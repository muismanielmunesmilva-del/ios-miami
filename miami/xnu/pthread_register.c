/* MIAMI static module-start adapter for Apple libpthread-514.100.2. */
#include <pexpert/arm64/board_config.h>
#if defined(MIAMI)
#include <kern/startup.h>
#include <kern/debug.h>
#include <kern/thread.h>
#include <sys/proc_internal.h>
#include <sys/pthread_shims.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>

extern kern_return_t pthread_start(kmod_info_t *, void *);
extern const struct pthread_functions_s pthread_internal_functions;

static void
miami_pthread_register(void)
{
    kern_return_t result = pthread_start(NULL, NULL);
    if (result != KERN_SUCCESS ||
        pthread_functions != &pthread_internal_functions || pthread_kern == NULL) {
        panic("MIAMI PTHREAD: callback registration failed");
    }
    kprintf("MIAMI PTHREAD: callbacks registered (libpthread-514.100.2)\n");
}
STARTUP(EARLY_BOOT, STARTUP_RANK_MIDDLE, miami_pthread_register);
#endif /* MIAMI */
