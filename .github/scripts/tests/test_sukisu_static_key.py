"""Regress the bool/static_key mismatch found in the shipped PAD 2 Pro Image."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "fix_sukisu_static_key.py"
SPEC = importlib.util.spec_from_file_location("fix_sukisu_static_key", SCRIPT)
assert SPEC and SPEC.loader
FIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIX)

# Definition, get/set and header declaration are verbatim from SukiSU b20dee7.
C_FIXTURE = r'''#define SU_PATH "/system/bin/su"
#define SH_PATH "/system/bin/sh"

bool ksu_su_compat_enabled __read_mostly = true;

static int su_compat_feature_get(u64 *value)
{
    *value = ksu_su_compat_enabled ? 1 : 0;
    return 0;
}

static int su_compat_feature_set(u64 value)
{
    bool enable = value != 0;
    ksu_su_compat_enabled = enable;
    pr_info("su_compat: set to %d\n", enable);
    return 0;
}

static const struct ksu_feature_handler su_compat_handler = {
    .feature_id = KSU_FEATURE_SU_COMPAT,
    .name = "su_compat",
    .get_handler = su_compat_feature_get,
    .set_handler = su_compat_feature_set,
};

#ifdef CONFIG_KSU_SUSFS
/* Other SUSFS functions omitted: none access this switch directly. */
#else
__attribute__((hot)) static __always_inline bool __is_su_allowed(const void **ptr_to_check)
{
    if (!ksu_su_compat_enabled)
        return false;
    (void)ptr_to_check;
    return true;
}
#endif
'''
H_FIXTURE = '''#ifndef __KSU_H_SUCOMPAT
#define __KSU_H_SUCOMPAT
#include <asm/ptrace.h>
#include <linux/types.h>

extern bool ksu_su_compat_enabled;

void ksu_sucompat_init(void);
void ksu_sucompat_exit(void);
#endif
'''
TYPES_STUB = '''#ifndef TEST_TYPES_H
#define TEST_TYPES_H
#include <stdbool.h>
#include <stdint.h>
typedef uint64_t u64;
#endif
'''
JUMP_STUB = '''#ifndef TEST_JUMP_LABEL_H
#define TEST_JUMP_LABEL_H
#include <stdbool.h>
struct static_key { int enabled; unsigned int padding; void *entries; };
struct static_key_true { struct static_key key; };
#define DEFINE_STATIC_KEY_TRUE(name) \\
    struct static_key_true name = { .key = { .enabled = 1 } }
static inline bool static_key_enabled(const struct static_key_true *key)
{ return key->key.enabled != 0; }
static inline void static_branch_enable(struct static_key_true *key)
{ key->key.enabled = 1; }
static inline void static_branch_disable(struct static_key_true *key)
{ key->key.enabled = 0; }
#define static_branch_likely(key) static_key_enabled(key)
#endif
'''
DRIVER = r'''#include "kernel/feature/sucompat.h"
#ifdef CONFIG_KSU_SUSFS
#include <linux/jump_label.h>
#endif
#define __read_mostly
#ifndef __always_inline
#define __always_inline inline
#endif
#define pr_info(...) ((void)0)
#define KSU_FEATURE_SU_COMPAT 1
struct ksu_feature_handler {
    int feature_id;
    const char *name;
    int (*get_handler)(u64 *);
    int (*set_handler)(u64);
};
#include "kernel/feature/sucompat.c"
int main(void)
{
    u64 value = 99;
    if (su_compat_handler.get_handler(&value) || value != 1) return 1;
#ifdef CONFIG_KSU_SUSFS
    if (sizeof(ksu_su_compat_enabled) != sizeof(struct static_key_true)) return 2;
    if (!static_branch_likely(&ksu_su_compat_enabled)) return 3;
#else
    if (sizeof(ksu_su_compat_enabled) != sizeof(bool)) return 4;
    if (!__is_su_allowed(0)) return 5;
#endif
    if (su_compat_handler.set_handler(0)) return 6;
    if (su_compat_handler.get_handler(&value) || value != 0) return 7;
#ifdef CONFIG_KSU_SUSFS
    if (static_branch_likely(&ksu_su_compat_enabled)) return 8;
#else
    if (__is_su_allowed(0)) return 9;
#endif
    if (su_compat_handler.set_handler(2)) return 10;
    if (su_compat_handler.set_handler(2)) return 11;
    if (su_compat_handler.get_handler(&value) || value != 1) return 12;
#ifdef CONFIG_KSU_SUSFS
    if (!static_branch_likely(&ksu_su_compat_enabled)) return 13;
#else
    if (!__is_su_allowed(0)) return 14;
#endif
    return 0;
}
'''


class StaticKeyRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sukisu-static-key-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = self.root / FIX.C_PATH
        self.h = self.root / FIX.H_PATH
        self.c.parent.mkdir(parents=True)
        self.c.write_text(C_FIXTURE, encoding="utf-8")
        self.h.write_text(H_FIXTURE, encoding="utf-8")

    def snapshot(self) -> tuple[bytes, bytes]:
        return self.c.read_bytes(), self.h.read_bytes()

    def rejected_unchanged(self) -> None:
        before = self.snapshot()
        with self.assertRaises(ValueError):
            FIX.repair(self.root)
        self.assertEqual(before, self.snapshot())

    def test_pinned_definition_reader_writer_and_header_repaired_together(self) -> None:
        self.assertTrue(FIX.repair(self.root))
        source = self.c.read_text(encoding="utf-8")
        header = self.h.read_text(encoding="utf-8")
        self.assertIn("DEFINE_STATIC_KEY_TRUE(ksu_su_compat_enabled);", source)
        self.assertIn("static_key_enabled(&ksu_su_compat_enabled) ? 1 : 0;", source)
        self.assertIn("static_branch_enable(&ksu_su_compat_enabled);", source)
        self.assertIn("static_branch_disable(&ksu_su_compat_enabled);", source)
        self.assertIn("extern struct static_key_true ksu_su_compat_enabled;", header)
        self.assertIn("#include <linux/jump_label.h>", source)
        self.assertIn("#else\nbool ksu_su_compat_enabled __read_mostly = true;", source)
        self.assertIn("#else\nextern bool ksu_su_compat_enabled;", header)

    def test_second_application_is_byte_identical(self) -> None:
        FIX.repair(self.root)
        before = self.snapshot()
        self.assertFalse(FIX.repair(self.root))
        self.assertEqual(before, self.snapshot())

    def test_unknown_getter_is_rejected_before_any_write(self) -> None:
        self.c.write_text(C_FIXTURE.replace("? 1 : 0", "? 3 : 0"), encoding="utf-8")
        self.rejected_unchanged()

    def test_unknown_setter_is_rejected_before_any_write(self) -> None:
        self.c.write_text(C_FIXTURE.replace("= enable;", "= !enable;"), encoding="utf-8")
        self.rejected_unchanged()

    def test_unknown_header_is_rejected_before_any_write(self) -> None:
        self.h.write_text(H_FIXTURE.replace("extern bool", "extern int"), encoding="utf-8")
        self.rejected_unchanged()

    def test_partial_repair_is_rejected(self) -> None:
        before, after = FIX.REPLACEMENTS[FIX.C_PATH][0]
        self.c.write_text(C_FIXTURE.replace(before, after), encoding="utf-8")
        self.rejected_unchanged()

    def test_new_external_user_is_rejected(self) -> None:
        path = self.root / "kernel/supercall/control.c"
        path.parent.mkdir()
        path.write_text("bool unsafe_read(void) { return ksu_su_compat_enabled; }\n", encoding="utf-8")
        self.rejected_unchanged()

    def test_new_local_user_is_rejected(self) -> None:
        with self.c.open("a", encoding="utf-8") as stream:
            stream.write("\nbool extra(void) { return ksu_su_compat_enabled; }\n")
        self.rejected_unchanged()

    def test_moved_non_susfs_reader_is_rejected(self) -> None:
        self.c.write_text(C_FIXTURE.replace("#else\n__attribute__", "#endif\n__attribute__"), encoding="utf-8")
        self.rejected_unchanged()

    def test_comments_and_string_literals_are_not_external_users(self) -> None:
        path = self.root / "kernel/diagnostics.c"
        path.write_text('/* ksu_su_compat_enabled */\nconst char *s = "ksu_su_compat_enabled";\n', encoding="utf-8")
        self.assertTrue(FIX.repair(self.root))

    def compile_fixture(self, susfs: bool, *, expect_success: bool = True) -> None:
        compiler = shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable; GitHub validation requires cc")
        for name, source in {
            "include/linux/types.h": TYPES_STUB,
            "include/linux/jump_label.h": JUMP_STUB,
            "include/asm/ptrace.h": "",
            "driver.c": DRIVER,
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        command = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Iinclude", "driver.c", "-o", "driver"]
        if susfs:
            command.insert(1, "-DCONFIG_KSU_SUSFS")
        compiled = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        if not expect_success:
            self.assertNotEqual(0, compiled.returncode, "old bool must not satisfy static-key callers")
            self.assertRegex(compiled.stderr, r"incompatible|pointer", compiled.stderr)
            return
        self.assertEqual(0, compiled.returncode, compiled.stdout + compiled.stderr)
        ran = subprocess.run([str(self.root / "driver")], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)

    def test_c_regression_original_bool_is_not_a_static_key(self) -> None:
        self.compile_fixture(True, expect_success=False)

    def test_c_susfs_default_true_disable_enable_and_repeated_enable(self) -> None:
        FIX.repair(self.root)
        self.compile_fixture(True)

    def test_c_without_susfs_preserves_original_bool_control(self) -> None:
        FIX.repair(self.root)
        self.compile_fixture(False)


if __name__ == "__main__":
    unittest.main()
