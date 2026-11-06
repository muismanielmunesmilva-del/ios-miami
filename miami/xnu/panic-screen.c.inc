/* First-panic display. Fixed framebuffer writes; no allocation or CPU state. */
#define MIAMI_PANIC_ROWS 18u
static volatile uint32_t *panic_screen_fb;
static uint32_t panic_screen_stride;
static volatile unsigned int panic_screen_latched;
static unsigned int panic_screen_row, panic_screen_col;

void
miami_panic_use_framebuffer(uint64_t base, uint64_t row_bytes)
{
    if (!base || (base & 3) || row_bytes < 4320 || row_bytes > 8192 ||
        (row_bytes & 3)) {
        return;
    }
    panic_screen_fb = (volatile uint32_t *)(uintptr_t)base;
    panic_screen_stride = (uint32_t)(row_bytes / 4);
}

unsigned int
miami_panic_reserved_rows(void)
{
    return panic_screen_latched ? MIAMI_PANIC_ROWS : 0;
}

static void
panic_screen_putc(char c)
{
    if (c == '\r') {
        panic_screen_col = 0;
        return;
    }
    if (c == '\n' || panic_screen_col >= EARLY_COLS) {
        panic_screen_col = 0;
        panic_screen_row++;
        if (c == '\n') {
            return;
        }
    }
    if (panic_screen_row >= MIAMI_PANIC_ROWS) {
        return;
    }
    const unsigned char *glyph = iso_font + (unsigned char)c * 16;
    for (unsigned int gy = 0; gy < 16; gy++) {
        for (unsigned int sy = 0; sy < EARLY_SCALE; sy++) {
            volatile uint32_t *line = panic_screen_fb +
                (panic_screen_row * EARLY_CELL_H + gy * EARLY_SCALE + sy) *
                panic_screen_stride + panic_screen_col * EARLY_CELL_W;
            for (unsigned int gx = 0; gx < 8; gx++) {
                uint32_t pixel = (glyph[gy] & (1u << gx)) ? 0xffffffffu : 0xff200000u;
                for (unsigned int sx = 0; sx < EARLY_SCALE; sx++) {
                    line[gx * EARLY_SCALE + sx] = pixel;
                }
            }
        }
    }
    panic_screen_col++;
}

static void
panic_screen_string(const char *text)
{
    /* A reason cannot consume unbounded reads or overwrite the fixed pane. */
    unsigned int remaining = MIAMI_PANIC_ROWS * EARLY_COLS;
    while (*text && remaining-- && panic_screen_row < MIAMI_PANIC_ROWS) {
        panic_screen_putc(*text++);
    }
}

static void
panic_screen_hex(const char *label, uint64_t value)
{
    static const char digits[] = "0123456789abcdef";
    panic_screen_string(label);
    panic_screen_string("0x");
    for (int shift = 60; shift >= 0; shift -= 4) {
        panic_screen_putc(digits[(value >> shift) & 15]);
    }
    panic_screen_putc('\n');
}

static unsigned int
panic_screen_begin(void)
{
    if (panic_screen_latched) {
        return 0;
    }
    if (!panic_screen_fb) {
        panic_screen_fb = early_fb;
        panic_screen_stride = early_stride;
    }
    if (!panic_screen_fb || panic_screen_stride < EARLY_WIDTH) {
        return 0;
    }
    /* Publish the protected rows before any normal console can clear them. */
    panic_screen_latched = 1;
    __asm__ volatile("dsb sy" ::: "memory");
    for (unsigned int y = 0; y < MIAMI_PANIC_ROWS * EARLY_CELL_H; y++) {
        for (unsigned int x = 0; x < EARLY_WIDTH; x++) {
            panic_screen_fb[y * panic_screen_stride + x] = 0xff200000u;
        }
    }
    panic_screen_row = panic_screen_col = 0;
    panic_screen_string("MIAMI FIRST PANIC v1\n");
    return 1;
}

void
miami_panic_saved_state(const char *reason, uint64_t pc, uint64_t lr,
    uint64_t sp, uint64_t fp, uint32_t esr, uint64_t far)
{
    if (!panic_screen_begin()) {
        return;
    }
    panic_screen_string("STATE: valid saved 64-bit exception\n");
    panic_screen_hex("PC  = ", pc);
    panic_screen_hex("LR  = ", lr);
    panic_screen_hex("ESR = ", esr);
    panic_screen_hex("FAR = ", far);
    panic_screen_hex("SP  = ", sp);
    panic_screen_hex("FP  = ", fp);
    panic_screen_string("REASON: ");
    panic_screen_string(reason);
    __asm__ volatile("dsb sy" ::: "memory");
}

void
miami_panic_reason(const char *format, va_list *args, uint64_t caller)
{
    if (!panic_screen_begin()) {
        return;
    }
    panic_screen_string("STATE: generic panic; no saved registers\n");
    panic_screen_hex("CALLER = ", caller);
    panic_screen_string("REASON:\n");
    va_list copy;
    va_copy(copy, *args);
    _doprnt(format, &copy, panic_screen_putc, 16);
    va_end(copy);
    __asm__ volatile("dsb sy" ::: "memory");
}
