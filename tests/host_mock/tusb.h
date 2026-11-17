#include "../usb_mock/tusb.h"
#include <stddef.h>
enum { TUSB_ROLE_HOST=3,TUSB_DIR_IN=1,TUSB_DESC_ENDPOINT=5,TUH_CFGID_RPI_PIO_USB_CONFIGURATION=1 };
static inline unsigned tu_edpt_dir(uint8_t ep) {return ep>>7;}
static inline uint16_t tu_edpt_packet_size(const tusb_desc_endpoint_t *ep) {return ep->wMaxPacketSize;}
typedef struct tuh_xfer_s {
    uint8_t daddr,ep_addr;
    tusb_control_request_t *setup;
    uint8_t *buffer;
    void (*complete_cb)(struct tuh_xfer_s *);
    uintptr_t user_data;
    xfer_result_t result;
    uint32_t actual_len;
} tuh_xfer_t;
bool tuh_configure(uint8_t port,uint32_t id,const void *config);
void tuh_task(void);
bool tuh_edpt_open(uint8_t addr,const tusb_desc_endpoint_t *ep);
bool tuh_edpt_abort_xfer(uint8_t addr,uint8_t ep);
bool tuh_control_xfer(tuh_xfer_t *xfer);
bool tuh_vid_pid_get(uint8_t addr,uint16_t *vid,uint16_t *pid);
bool tud_cdc_connected(void);
bool tud_inited(void);
uint32_t tud_cdc_write(const void *data,uint32_t count);
void tud_cdc_write_flush(void);
