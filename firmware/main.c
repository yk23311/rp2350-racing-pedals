#include "pedal.h"
#include "console.h"
#include "hal.h"
#include "storage.h"
#include "usb.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include <string.h>
static console_input_t input;
static char response[CONSOLE_RESPONSE_SIZE];
static size_t tx_pos,tx_len;
void tud_cdc_line_state_cb(uint8_t instance,bool dtr,bool rts) {
    (void)rts;
    if(instance==0 && !dtr) {
        tx_pos=tx_len=0; memset(&input,0,sizeof(input));
        tud_cdc_write_clear(); tud_cdc_read_flush();
    }
}
static bool save_config(void *context,const pedal_config_t *config) {
    (void)context;
    return pedal_usb_quiet() && storage_save(config);
}
int main(void) {
    pedal_config_t config; storage_load(&config);
    pedal_t pedal; pedal_init(&pedal,&config);
    pedal_hal_init(); pedal_usb_init(&pedal);
    pedal_button_t button={0};
    uint64_t next_sample=0;
    while(true) {
        pedal_usb_task();
        uint64_t now=time_us_64();
        if(now>=next_sample) {
            next_sample=now+1000;
            uint16_t raw[2]; pedal_hal_read(raw); pedal_sample(&pedal,raw);
            if(pedal_button_update(&button,pedal_hal_button(),to_ms_since_boot(get_absolute_time())))
                pedal_mode(&pedal,pedal.mode==PEDAL_JOYSTICK?PEDAL_KEYBOARD:PEDAL_JOYSTICK);
        }
        if(!tud_cdc_connected()) {
            tx_pos=tx_len=0; memset(&input,0,sizeof(input));
            tud_cdc_write_clear(); tud_cdc_read_flush();
        }
        else {
            if(tx_pos<tx_len) tx_pos+=tud_cdc_write(response+tx_pos,(uint32_t)(tx_len-tx_pos));
            tud_cdc_write_flush();
            /* Bounded service work per iteration; do not starve ADC/USB on a flood. */
            unsigned budget=64;
            while(tx_pos==tx_len && budget-- && tud_cdc_available()) {
                char ch=(char)tud_cdc_read_char();
                if(console_feed(&input,ch,&pedal,save_config,NULL,response)) {
                    tx_pos=0; tx_len=strlen(response); break;
                }
            }
        }
        tight_loop_contents();
    }
}
