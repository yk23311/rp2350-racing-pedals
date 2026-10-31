#include "host.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include "host/usbh.h"
#include "host/usbh_pvt.h"
#include "host/hcd.h"
#include "pio_usb.h"
#include "xinput_pad.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define HOST_LOG_SIZE 160u
#define HOST_IN_BUFFER_SIZE 64u
#define HOST_HANDSHAKE_BUFFER_SIZE 64u

typedef enum {
    HOST_HS_IDLE = 0,
    HOST_HS_XUSB10_EE,
    HOST_HS_XUSB10_20,
    HOST_HS_MAGIC,
    HOST_HS_DONE
} host_handshake_state_t;

typedef struct {
    bool opened;
    uint8_t dev_addr;
    uint8_t itf_num;
    uint8_t ep_in;
    uint8_t ep_out;
    uint16_t ep_in_size;
    uint16_t ep_out_size;
} host_interface_t;

static bridge_t host_state;
static host_interface_t host_itf;
static uint8_t host_in_buffer[HOST_IN_BUFFER_SIZE];
static uint8_t host_handshake_buffer[HOST_HANDSHAKE_BUFFER_SIZE];
static tusb_control_request_t host_handshake_request;
static host_handshake_state_t handshake_state;
static bool handshake_pending;
static uint32_t host_report_count;
static uint32_t host_invalid_reports;
static uint32_t host_last_status_ms;
static uint32_t host_last_idle_ms;
static uint32_t host_last_report_ms;
static volatile uint32_t host_event_count;
static volatile uint32_t host_attach_events;
static volatile uint32_t host_remove_events;
static volatile uint32_t host_last_event_id;
static bool host_banner_logged;
static bool host_init_ok;

static void host_handshake_complete(tuh_xfer_t *xfer);

static uint32_t host_now_ms(void) {
    return to_ms_since_boot(get_absolute_time());
}

static void host_log(const char *format, ...) {
    if (!tud_cdc_connected()) return;
    char line[HOST_LOG_SIZE];
    va_list args;
    va_start(args, format);
    int length = vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    if (length <= 0) return;
    if ((size_t)length > sizeof(line) - 1u) length = (int)(sizeof(line) - 1u);
    (void)tud_cdc_write(line, (uint32_t)length);
    (void)tud_cdc_write("\r\n", 2);
    tud_cdc_write_flush();
}

static void host_log_hex(const char *prefix, const uint8_t *data, uint16_t length) {
    char line[HOST_LOG_SIZE];
    int used = snprintf(line, sizeof(line), "%s", prefix);
    if (used < 0) return;
    for (uint16_t i = 0; i < length && (size_t)used + 3u < sizeof(line); i++) {
        used += snprintf(line + used, sizeof(line) - (size_t)used, "%02X", data[i]);
    }
    host_log("%s", line);
}

static void host_arm_in(void) {
    if (!host_itf.opened || host_itf.ep_in == 0) return;
    if (usbh_edpt_busy(host_itf.dev_addr, host_itf.ep_in)) return;
    if (!usbh_edpt_claim(host_itf.dev_addr, host_itf.ep_in)) return;
    if (!usbh_edpt_xfer(host_itf.dev_addr, host_itf.ep_in, host_in_buffer,
                        host_itf.ep_in_size)) {
        usbh_edpt_release(host_itf.dev_addr, host_itf.ep_in);
    }
}

static void host_handshake_finished(void) {
    handshake_state = HOST_HS_DONE;
    handshake_pending = false;
    bridge_host_handshake_done(&host_state, host_now_ms());
    host_arm_in();
}

static void host_handshake_fail_step(void) {
    if (handshake_state == HOST_HS_XUSB10_EE) {
        handshake_state = HOST_HS_XUSB10_20;
        handshake_pending = true;
    } else {
        host_handshake_finished();
    }
}

static void host_handshake_start_step(void) {
    uint8_t dev_addr = host_itf.dev_addr;
    if (!host_itf.opened || dev_addr == 0) {
        host_handshake_finished();
        return;
    }
    handshake_pending = false;
    memset(&host_handshake_request, 0, sizeof(host_handshake_request));
    switch (handshake_state) {
        case HOST_HS_XUSB10_EE:
        case HOST_HS_XUSB10_20:
            host_handshake_request.bmRequestType = 0xC0;
            host_handshake_request.bRequest =
                handshake_state == HOST_HS_XUSB10_EE ? 0xEE : 0x20;
            host_handshake_request.wValue = 0;
            host_handshake_request.wIndex = 4;
            host_handshake_request.wLength = 40;
            break;
        case HOST_HS_MAGIC:
            host_handshake_request.bmRequestType = 0xC1;
            host_handshake_request.bRequest = 0x01;
            host_handshake_request.wValue = 0x0100;
            host_handshake_request.wIndex = 0;
            host_handshake_request.wLength = 20;
            break;
        default:
            host_handshake_finished();
            return;
    }
    tuh_xfer_t xfer = {
        .daddr = dev_addr,
        .ep_addr = 0,
        .setup = &host_handshake_request,
        .buffer = host_handshake_buffer,
        .complete_cb = host_handshake_complete,
        .user_data = 0,
    };
    if (!tuh_control_xfer(&xfer)) {
        host_log("[HOST] handshake step %d not accepted", (int)handshake_state);
        host_handshake_fail_step();
    }
}

static void host_handshake_complete(tuh_xfer_t *xfer) {
    if (xfer == NULL) return;
    if (xfer->result != XFER_RESULT_SUCCESS) {
        host_log("[HOST] handshake step %d failed: %d", (int)handshake_state, (int)xfer->result);
        host_handshake_fail_step();
        return;
    }
    host_log("[HOST] handshake step %d ok, len=%u", (int)handshake_state,
             (unsigned)xfer->actual_len);
    if (handshake_state == HOST_HS_XUSB10_EE || handshake_state == HOST_HS_XUSB10_20) {
        host_log_hex("[HOST] compat: ", host_handshake_buffer,
                     xfer->actual_len > 20u ? 20u : (uint16_t)xfer->actual_len);
        handshake_state = HOST_HS_MAGIC;
        handshake_pending = true;
        return;
    }
    host_handshake_finished();
}

static void host_start_handshake(uint8_t dev_addr, uint16_t vid, uint16_t pid) {
    (void)dev_addr;
    handshake_state = HOST_HS_XUSB10_EE;
    handshake_pending = true;
    host_log("[HOST] handshake for %04X:%04X", vid, pid);
}

static bool host_xinput_init(void) {
    memset(&host_itf, 0, sizeof(host_itf));
    return true;
}

static bool host_xinput_open(uint8_t rhport, uint8_t dev_addr,
                             const tusb_desc_interface_t *desc_itf, uint16_t max_len) {
    (void)rhport;
    if (desc_itf == NULL || host_itf.opened) return false;
    if (desc_itf->bInterfaceClass != 0xFF || desc_itf->bInterfaceSubClass != 0x5D ||
        desc_itf->bInterfaceProtocol != 0x01) {
        return false;
    }
    host_interface_t candidate;
    memset(&candidate, 0, sizeof(candidate));
    candidate.dev_addr = dev_addr;
    candidate.itf_num = desc_itf->bInterfaceNumber;
    const uint8_t *bytes = (const uint8_t *)desc_itf;
    uint16_t pos = 0;
    while (pos + 2u <= max_len) {
        uint8_t length = bytes[pos];
        uint8_t type = bytes[pos + 1u];
        if (length < 2u || (uint16_t)(pos + length) > max_len) break;
        if (type == TUSB_DESC_ENDPOINT && length >= 7u) {
            const tusb_desc_endpoint_t *ep = (const tusb_desc_endpoint_t *)(bytes + pos);
            if (tu_edpt_dir(ep->bEndpointAddress) == TUSB_DIR_IN) {
                if (candidate.ep_in != 0) return false;
                candidate.ep_in = ep->bEndpointAddress;
                candidate.ep_in_size = tu_edpt_packet_size(ep);
            } else {
                if (candidate.ep_out != 0) return false;
                candidate.ep_out = ep->bEndpointAddress;
                candidate.ep_out_size = tu_edpt_packet_size(ep);
            }
            if (!tuh_edpt_open(dev_addr, ep)) return false;
        }
        pos = (uint16_t)(pos + length);
    }
    if (candidate.ep_in == 0) return false;
    if (candidate.ep_in_size < XINPUT_PAD_REPORT_SIZE) return false;
    candidate.opened = true;
    host_itf = candidate;
    host_log("[HOST] xinput interface %u in=%02X/%u out=%02X/%u",
             host_itf.itf_num, host_itf.ep_in, host_itf.ep_in_size, host_itf.ep_out,
             host_itf.ep_out_size);
    return true;
}

static bool host_xinput_set_config(uint8_t dev_addr, uint8_t itf_num) {
    if (host_itf.opened && host_itf.dev_addr == dev_addr && host_itf.itf_num == itf_num) {
        host_arm_in();
    }
    usbh_driver_set_config_complete(dev_addr, itf_num);
    return true;
}

static bool host_xinput_xfer_cb(uint8_t dev_addr, uint8_t ep_addr, xfer_result_t result,
                                uint32_t xferred_bytes) {
    if (!host_itf.opened || dev_addr != host_itf.dev_addr) return false;
    if (ep_addr == host_itf.ep_in) {
        if (result == XFER_RESULT_SUCCESS) {
            xinput_pad_t pad;
            if (xinput_pad_parse_wired(host_in_buffer, (uint16_t)xferred_bytes, &pad)) {
                host_report_count++;
                host_last_report_ms = host_now_ms();
                bridge_host_report(&host_state, &pad, host_last_report_ms);
                if (host_report_count <= 8u || (host_report_count % 250u) == 0u) {
                    host_log("[HOST] pad n=%lu btn=%04X LT=%u RT=%u LX=%d LY=%d RX=%d RY=%d",
                             (unsigned long)host_report_count, pad.buttons, pad.lt, pad.rt,
                             pad.lx, pad.ly, pad.rx, pad.ry);
                }
            } else if (xferred_bytes < 20u) {
                host_log("[HOST] short report len=%u %02X %02X", (unsigned)xferred_bytes,
                         host_in_buffer[0], xferred_bytes > 1u ? host_in_buffer[1] : 0u);
            } else {
                host_invalid_reports++;
                if (host_invalid_reports <= 5u || (host_invalid_reports % 250u) == 0u) {
                    host_log("[HOST] reject report len=%u %02X %02X", (unsigned)xferred_bytes,
                             host_in_buffer[0], host_in_buffer[1]);
                }
            }
        } else {
            host_log("[HOST] IN error %d", (int)result);
        }
        host_arm_in();
        return true;
    }
    if (ep_addr == host_itf.ep_out) {
        return true;
    }
    return false;
}

static void host_xinput_close(uint8_t dev_addr) {
    if (host_itf.opened && host_itf.dev_addr == dev_addr) {
        host_itf.opened = false;
    }
}

static const usbh_class_driver_t host_xinput_driver = {
    .name = "XInputHost",
    .init = host_xinput_init,
    .open = host_xinput_open,
    .set_config = host_xinput_set_config,
    .xfer_cb = host_xinput_xfer_cb,
    .close = host_xinput_close,
};

const usbh_class_driver_t *usbh_app_driver_get_cb(uint8_t *driver_count) {
    if (driver_count != NULL) *driver_count = 1;
    return &host_xinput_driver;
}

void tuh_event_hook_cb(uint8_t rhport, uint32_t eventid, bool in_isr) {
    (void)rhport;
    (void)in_isr;
    host_event_count++;
    host_last_event_id = eventid;
    if (eventid == HCD_EVENT_DEVICE_ATTACH) host_attach_events++;
    else if (eventid == HCD_EVENT_DEVICE_REMOVE) host_remove_events++;
}

void host_init(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_init(&host_state, &config, host_now_ms());
    memset(&host_itf, 0, sizeof(host_itf));
    handshake_state = HOST_HS_IDLE;
    handshake_pending = false;
    host_report_count = 0;
    host_invalid_reports = 0;
    host_event_count = 0;
    host_attach_events = 0;
    host_remove_events = 0;
    host_last_event_id = 0;
    host_banner_logged = false;
    host_init_ok = false;
    host_last_status_ms = host_now_ms();
    host_last_idle_ms = host_now_ms();
    host_last_report_ms = host_now_ms();

    pio_usb_configuration_t config_pio = PIO_USB_DEFAULT_CONFIG;
    config_pio.pin_dp = 12;
    bool ok = tuh_configure(1, TUH_CFGID_RPI_PIO_USB_CONFIGURATION, &config_pio);
    tusb_rhport_init_t init = {.role = TUSB_ROLE_HOST, .speed = TUSB_SPEED_FULL};
    ok = tusb_init(1, &init) && ok;
    host_init_ok = ok;
}

void host_task(void) {
    tuh_task();
    if (handshake_pending) host_handshake_start_step();
    uint32_t now = host_now_ms();
    bridge_tick(&host_state, now);
    if (!host_banner_logged && tud_cdc_connected()) {
        host_banner_logged = true;
        host_log("[HOST] probe boot init=%d pin=12", host_init_ok ? 1 : 0);
    }
    if ((uint32_t)(now - host_last_status_ms) >= 500u) {
        host_last_status_ms = now;
        if (host_state.host_seen) {
            host_log("[HOST] state=%d reports=%lu invalid=%lu age=%lu timeouts=%lu events=%lu attach=%lu remove=%lu",
                     (int)host_state.state, (unsigned long)host_report_count,
                     (unsigned long)host_invalid_reports,
                     (unsigned long)(now - host_last_report_ms),
                     (unsigned long)host_state.timeouts,
                     (unsigned long)host_event_count,
                     (unsigned long)host_attach_events,
                     (unsigned long)host_remove_events);
        } else if ((uint32_t)(now - host_last_idle_ms) >= 2000u) {
            host_last_idle_ms = now;
            host_log("[HOST] waiting events=%lu attach=%lu remove=%lu last=%lu",
                     (unsigned long)host_event_count,
                     (unsigned long)host_attach_events,
                     (unsigned long)host_remove_events,
                     (unsigned long)host_last_event_id);
        }
    }
}

const bridge_t *host_bridge(void) {
    return &host_state;
}

bool host_ready(void) {
    return bridge_host_ready(&host_state);
}

void tuh_mount_cb(uint8_t dev_addr) {
    uint16_t vid = 0;
    uint16_t pid = 0;
    (void)tuh_vid_pid_get(dev_addr, &vid, &pid);
    if (!host_itf.opened || host_itf.dev_addr != dev_addr) {
        host_log("[HOST] mount %04X:%04X addr=%u without XInput interface", vid, pid, dev_addr);
        return;
    }
    host_log("[HOST] mount %04X:%04X addr=%u", vid, pid, dev_addr);
    bridge_host_mounted(&host_state, vid, pid, host_now_ms());
    handshake_state = HOST_HS_IDLE;
    if (vid == 0x20BC) {
        host_start_handshake(dev_addr, vid, pid);
    } else {
        host_handshake_finished();
    }
}

void tuh_umount_cb(uint8_t dev_addr) {
    if (host_itf.opened && host_itf.dev_addr == dev_addr) {
        host_log("[HOST] umount addr=%u", dev_addr);
        bridge_host_unmounted(&host_state, host_now_ms());
        host_itf.opened = false;
        handshake_state = HOST_HS_IDLE;
        handshake_pending = false;
    }
}
