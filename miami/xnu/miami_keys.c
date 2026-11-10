/*
 * Minimal polled MIAMI hardware keys driver (Read-Only SPMI observer).
 *
 * Motorola Edge 30 Neo (XT2245-1 / SM6375 holi / Blair):
 * - SPMI Arbiter v5:
 *     core:   0x01c40000 (0x2000)
 *     cnfg:   0x01c0a000 (0x1000)
 *     obs:    0x03e00000 (0x10000)
 * - Keys:
 *     Power button:       PM6125 (SID 0), PON peripheral 0x0800, RT_STS (0x0810) bit 0
 *     Volume down button: PM6125 (SID 0), PON peripheral 0x0800, RT_STS (0x0810) bit 1 (resin)
 *     Volume up button:   PMR735A (SID 4), GPIO 1 (0x8800 block -> RT_STS 0xc110)
 *
 * PMIC access is READ ONLY: the sole MMIO operation issues EXT_READL on the
 * observer channel. No PMIC write, configuration, IRQ acknowledge or reset writes exist.
 */
#if defined(ARM64_BOARD_CONFIG_MIAMI)
#include <sys/param.h>
#include <sys/systm.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <kern/sched_prim.h>
#include <machine/machine_routines.h>
#include <pexpert/pexpert.h>

extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
extern void miami_hid_key(int key, int down);
void miami_keys_init(void);

#define KEYS_CORE_PA     0x01c40000u
#define KEYS_OBS_PA      0x03e00000u
#define KEYS_CNFG_PA     0x01c0a000u
#define KEYS_PON_RT      0x0810u
#define KEYS_GPIO_RT     0xc110u
#define KEYS_NO_APID     0xffffu

static vm_offset_t keys_core, keys_obs, keys_cnfg;
static uint16_t keys_pon_apid = KEYS_NO_APID, keys_gpio_apid = KEYS_NO_APID;
static uint32_t keys_version, keys_last_status;
static bool keys_started;
static int keys_sleep_chan;

static uint32_t
keys_rd(vm_offset_t base, uint32_t off)
{
	uint32_t v = *(volatile uint32_t *)(base + off);
	__asm__ volatile("dmb oshld" ::: "memory");
	return v;
}

/* SPMI v5 can map one PPID more than once; prefer the apps-owned entry. */
static uint16_t
keys_find_apid(uint16_t ppid, uint32_t count)
{
	uint16_t found = KEYS_NO_APID;
	for (uint32_t i = 0; i < count; ++i) {
		uint32_t map = keys_rd(keys_core, 0x900u + 4u * i);
		if (map == 0 || ((map >> 8) & 0xfffu) != ppid) {
			continue;
		}
		uint32_t owner = keys_rd(keys_cnfg, 0x700u + 4u * i) & 7u;
		if (found == KEYS_NO_APID || owner == 0) {
			found = (uint16_t)i;
		}
	}
	return found;
}

static bool
keys_read(uint16_t apid, uint16_t addr, uint8_t *out)
{
	if (apid == KEYS_NO_APID) {
		return false;
	}
	uint32_t off = 0x80u * apid; /* obs + EE(0)*0x10000 */
	uint32_t cmd = (1u << 27) | ((uint32_t)(addr & 0xffu) << 4);
	__asm__ volatile("dmb oshst" ::: "memory");
	*(volatile uint32_t *)(keys_obs + off) = cmd; /* EXT_READL, one byte */
	__asm__ volatile("dsb osh" ::: "memory");
	for (unsigned i = 0; i < 1000; ++i) {
		keys_last_status = keys_rd(keys_obs, off + 0x08u);
		if (keys_last_status & 1u) {
			if (keys_last_status & 0x0eu) {
				return false;
			}
			*out = (uint8_t)keys_rd(keys_obs, off + 0x18u);
			return true;
		}
		delay(1);
	}
	return false;
}

static void
keys_wait(void)
{
	uint64_t deadline;
	clock_interval_to_deadline(20, NSEC_PER_MSEC, &deadline);
	(void)assert_wait_deadline(&keys_sleep_chan, THREAD_UNINT, deadline);
	thread_block(THREAD_CONTINUE_NULL);
}

static void
keys_thread(void *arg, wait_result_t result)
{
	int state[3] = {0, 0, 0};
	unsigned errors = 0;
	(void)arg;
	(void)result;
	for (;;) {
		uint8_t pon = 0, gpio = 0;
		bool pok = keys_read(keys_pon_apid, KEYS_PON_RT, &pon);
		bool gok = keys_read(keys_gpio_apid, KEYS_GPIO_RT, &gpio);
		/*
		 * Key mapping:
		 * 0 = Power (PON bit 0)
		 * 1 = Volume Up (GPIO1 on PMR735A SID 4, active low)
		 * 2 = Volume Down (PON bit 1, resin)
		 */
		int now[3] = {!!(pon & 1u), !(gpio & 1u), !!(pon & 2u)};
		if (!pok || !gok) {
			if ((errors++ % 250u) == 0) {
				printf("MIAMI KEYS: read error pon-ok=%d gpio-ok=%d arb-status=%#x\n",
				    pok, gok, keys_last_status);
			}
		} else {
			errors = 0;
		}
		for (int k = 0; k < 3; ++k) {
			if ((k == 1 ? gok : pok) && now[k] != state[k]) {
				state[k] = now[k];
				printf("MIAMI KEYS: key=%d down=%d pon=%#x gpio4:c110=%#x\n",
				    k, state[k], pon, gpio);
				miami_hid_key(k, state[k]);
			}
		}
		keys_wait();
	}
}

void
miami_keys_init(void)
{
	int enabled = 1;
	thread_t thread;
	if (keys_started) {
		return;
	}
	keys_started = true;
	(void)PE_parse_boot_argn("miamikeys", &enabled, sizeof(enabled));
	if (!enabled) {
		printf("MIAMI KEYS: disabled (miamikeys=0)\n");
		return;
	}
	keys_core = ml_io_map(KEYS_CORE_PA, 0x2000);
	keys_cnfg = ml_io_map(KEYS_CNFG_PA, 0x1000);
	keys_obs = ml_io_map(KEYS_OBS_PA, 0x10000);
	if (!keys_core || !keys_cnfg || !keys_obs) {
		printf("MIAMI KEYS: MMIO mapping failed\n");
		return;
	}
	keys_version = keys_rd(keys_core, 0);
	uint32_t count = keys_rd(keys_core, 4) & 0x7ffu;
	if (keys_version < 0x50000000u || keys_version >= 0x70000000u ||
	    count == 0 || count > 512) {
		printf("MIAMI KEYS: unsupported arbiter version=%#x apids=%u\n",
		    keys_version, count);
		return;
	}
	/* PPID 0x008: PM6125 (SID 0) PON (0x0800) */
	keys_pon_apid = keys_find_apid(0x008, count);
	/* PPID 0x4c1: PMR735A (SID 4) GPIO 1 (0xc100 / 0x8800 block) */
	keys_gpio_apid = keys_find_apid(0x4c1, count);

	uint8_t pon = 0, gpio = 0;
	bool pok = keys_read(keys_pon_apid, KEYS_PON_RT, &pon);
	bool gok = keys_read(keys_gpio_apid, KEYS_GPIO_RT, &gpio);
	printf("MIAMI KEYS: arb=%#x apids=%u pon-apid=%u gpio4-apid=%u pon=%#x/%d gpio=%#x/%d\n",
	    keys_version, count, keys_pon_apid, keys_gpio_apid,
	    pon, pok, gpio, gok);

	if (!pok && !gok) {
		printf("MIAMI KEYS: no readable keys; polling retained for recovery\n");
	}
	kern_return_t kr = kernel_thread_start(keys_thread, NULL, &thread);
	if (kr == KERN_SUCCESS) {
		thread_deallocate(thread);
	} else {
		printf("MIAMI KEYS: kernel_thread_start failed %d\n", kr);
	}
}
#endif /* ARM64_BOARD_CONFIG_MIAMI */
