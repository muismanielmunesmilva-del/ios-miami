/*
 * MIAMI: Qualcomm Snapdragon 695 (SM6375 / holi / Blair) USB state probe.
 *
 * Hardware mapping:
 * - Synopsys DWC3 at 0x04e00000 (size 0xcd00) behind Qualcomm dwc-usb3-msm wrapper
 * - GCC clock controller at 0x01400000 (size 0x1f0000)
 * - SNPS Femto USB HS PHY at 0x0162b000 (size 0x114)
 * - USB3 QMP combo SS PHY at 0x01630000 (size 0x3000)
 *
 * Mode: STRICT READ-ONLY STATE PROBE
 * This driver never issues any register writes to clocks, PHYs, or the DWC3 core.
 * It reads the live hardware registers left active by the bootloader/fastboot:
 * - GEVNTADR, GEVNTSIZ, GEVNTCOUNT (event buffer status)
 * - GHWPARAMS0, GHWPARAMS1, GSNPSID (Synopsys core identity & revision)
 * - DSTS (device speed and link state)
 */
#if defined(ARM64_BOARD_CONFIG_MIAMI)
#include <sys/param.h>
#include <sys/systm.h>
#include <pexpert/pexpert.h>

extern vm_offset_t ml_io_map(vm_offset_t, vm_size_t);
void miami_usb_probe(void);

#define GCC_PA                  0x01400000u
#define GCC_SIZE                0x001f0000u

#define DWC3_PA                 0x04e00000u
#define DWC3_SIZE               0x0000d000u

#define HSPHY_PA                0x0162b000u
#define HSPHY_SIZE              0x00000200u

static uint32_t
usb_rd(vm_offset_t base, uint32_t off)
{
	uint32_t v = *(volatile uint32_t *)(base + off);
	__asm__ volatile("dmb oshld" ::: "memory");
	return v;
}

void
miami_usb_probe(void)
{
	int enabled = 1;
	PE_parse_boot_argn("miamiusb", &enabled, sizeof(enabled));
	if (!enabled) {
		printf("MIAMI USB: probe disabled (miamiusb=0)\n");
		return;
	}

	vm_offset_t dwc = ml_io_map(DWC3_PA, DWC3_SIZE);
	if (!dwc) {
		printf("MIAMI USB: failed to map DWC3 registers at 0x%08x\n", DWC3_PA);
		return;
	}

	/* Read core ID registers */
	uint32_t snpsid   = usb_rd(dwc, 0xc120); /* GSNPSID */
	uint32_t hwparam0 = usb_rd(dwc, 0xc140); /* GHWPARAMS0 */
	uint32_t hwparam1 = usb_rd(dwc, 0xc144); /* GHWPARAMS1 */
	uint32_t dsts     = usb_rd(dwc, 0x700c); /* DSTS (Device Status) */

	/* Read event buffer 0 state */
	uint32_t evnt_adr_l = usb_rd(dwc, 0xc400);
	uint32_t evnt_adr_h = usb_rd(dwc, 0xc404);
	uint32_t evnt_siz   = usb_rd(dwc, 0xc408);
	uint32_t evnt_cnt   = usb_rd(dwc, 0xc40c);

	printf("MIAMI USB: DWC3 GSNPSID=0x%08x GHWPARAMS0=0x%08x GHWPARAMS1=0x%08x DSTS=0x%08x\n",
	    snpsid, hwparam0, hwparam1, dsts);
	printf("MIAMI USB: DWC3 GEVNTADR=0x%08x%08x GEVNTSIZ=0x%08x GEVNTCOUNT=0x%08x\n",
	    evnt_adr_h, evnt_adr_l, evnt_siz, evnt_cnt);

	vm_offset_t hsphy = ml_io_map(HSPHY_PA, HSPHY_SIZE);
	if (hsphy) {
		uint32_t phy_ctrl = usb_rd(hsphy, 0x00);
		printf("MIAMI USB: HSPHY at 0x%08x mapped, reg0=0x%08x\n", HSPHY_PA, phy_ctrl);
	}
}
#endif /* ARM64_BOARD_CONFIG_MIAMI */
