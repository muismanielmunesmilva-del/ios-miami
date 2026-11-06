ENTRY(_head)
SECTIONS {
    . = 0;
    .text : { KEEP(*(.text.head)) *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    . = ALIGN(16);
    _bss_start = .;
    .bss : { *(.bss*) *(COMMON) }
    . = ALIGN(16);
    _bss_end = .;
    . += 0x8000;
    _stack_top = .;
    /* Keep the initial stack/zeroed state close to entry, independently of
     * the embedded kernel size. The payload remains disjoint and read-only. */
    . = ALIGN(16384);
    _payload_start = .;
    .payload : { KEEP(*(.payload)) }
    _payload_end = .;
    . = ALIGN(16384);
    _end = .;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
