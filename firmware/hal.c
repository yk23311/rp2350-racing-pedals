#include "hal.h"
#include "hardware/adc.h"
#include "pico/stdlib.h"
void pedal_hal_init(void) {
    adc_init();
    adc_gpio_init(PEDAL_THROTTLE_GPIO); adc_gpio_init(PEDAL_BRAKE_GPIO);
    gpio_init(PEDAL_MODE_GPIO); gpio_set_dir(PEDAL_MODE_GPIO,GPIO_IN); gpio_pull_up(PEDAL_MODE_GPIO);
}
void pedal_hal_read(uint16_t raw[2]) {
    for(unsigned i=0;i<2;i++) {
        adc_select_input(i);
        (void)adc_read(); /* discard first conversion after switching channels */
        raw[i]=adc_read();
    }
}
bool pedal_hal_button(void) { return !gpio_get(PEDAL_MODE_GPIO); }
