"""Keep the first panic reason/registers visible without changing panic handling."""
from pathlib import Path


def stage(tree, edit):
    early = 'osfmk/arm64/miami_early.c'
    fragment = Path(__file__).with_name('panic-screen.c.inc').read_text()
    edit(tree, early, '\n#endif /* MIAMI */\n', '\n' + fragment + '\n#endif /* MIAMI */\n')
    edit(tree, 'osfmk/arm64/miami_early.h',
         'void miami_early_panic(const char *fmt, va_list *args);',
         '''void miami_early_panic(const char *fmt, va_list *args);
void miami_panic_use_framebuffer(uint64_t base, uint64_t row_bytes);
unsigned int miami_panic_reserved_rows(void);
void miami_panic_saved_state(const char *reason, uint64_t pc, uint64_t lr,
    uint64_t sp, uint64_t fp, uint32_t esr, uint64_t far);
void miami_panic_reason(const char *format, va_list *args, uint64_t caller);''')
    edit(tree, 'osfmk/kern/debug.c',
         'miami_early_panic(panic_format_str, panic_args);',
         'miami_panic_reason(panic_format_str, panic_args, (uint64_t)panic_caller);')
    edit(tree, 'osfmk/arm64/sleh.c', '#include <pexpert/arm64/board_config.h>\n',
         '#include <pexpert/arm64/board_config.h>\n#include <arm64/miami_early.h>\n')
    edit(tree, 'osfmk/arm64/sleh.c',
         '\tss_valid = is_saved_state64(ss);\n\tarm_saved_state64_t *state = saved_state64(ss);\n',
         '''\tss_valid = is_saved_state64(ss);
\tarm_saved_state64_t *state = saved_state64(ss);
#if defined(MIAMI)
\tif (ss_valid) {
\t\tmiami_panic_saved_state(msg, state->pc, state->lr, state->sp,
\t\t    state->fp, state->esr, state->far);
\t}
#endif
''')
    # Even the early console must not wrap over a captured first panic.
    edit(tree, early, '\tif (!early_started) {',
         '\tunsigned int first = miami_panic_reserved_rows();\n'
         '\tif (early_row < first) { early_row = first; early_col = 0; }\n'
         '\tif (!early_started) {')
    edit(tree, early, '\t\tearly_row = (early_row + 1) % EARLY_ROWS;',
         '\t\tearly_row++;\n\t\tif (early_row >= EARLY_ROWS) { early_row = first; }')
    serial = 'pexpert/arm/pe_serial.c'
    edit(tree, serial, 'static void\nfbcon_clear_row(uint32_t row)\n{', '''static uint32_t
fbcon_first_row(void)
{
#if defined(MIAMI)
    return miami_panic_reserved_rows();
#else
    return 0;
#endif
}

static void
fbcon_clear_row(uint32_t row)
{
    if (row < fbcon_first_row()) { return; }''')
    edit(tree, serial, '''\tfbcon_col = 0;
\tfbcon_row = (fbcon_row + 1) % fbcon_rows;
\tfbcon_clear_row(fbcon_row);
\tfbcon_clear_row((fbcon_row + 1) % fbcon_rows);''', '''\tfbcon_col = 0;
\tuint32_t first = fbcon_first_row();
\tfbcon_row++;
\tif (fbcon_row >= fbcon_rows || fbcon_row < first) { fbcon_row = first; }
\tfbcon_clear_row(fbcon_row);
\tfbcon_clear_row(fbcon_row + 1 >= fbcon_rows ? first : fbcon_row + 1);''')
    edit(tree, serial, '\tfbcon_col = fbcon_row = 0;',
         '\tfbcon_col = 0;\n\tfbcon_row = fbcon_first_row();')
    edit(tree, serial, 'fbcon_transmit_data(uint8_t c)\n{', '''fbcon_transmit_data(uint8_t c)
{
    uint32_t first = fbcon_first_row();
    if (fbcon_row < first) { fbcon_row = first; fbcon_col = 0; }''')
    edit(tree, serial, '\tif (fbcon_base != NULL) {\n\t\tregister_serial_functions',
         '''\tif (fbcon_base != NULL) {
#if defined(MIAMI)
\t\tif (fbcon_width == 1080 && fbcon_height == 2400) {
\t\t\tmiami_panic_use_framebuffer((uint64_t)(uintptr_t)fbcon_base, fbcon_stride);
\t\t}
#endif
\t\tregister_serial_functions''')
