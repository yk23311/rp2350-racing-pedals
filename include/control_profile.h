#ifndef CONTROL_PROFILE_H
#define CONTROL_PROFILE_H
#include "console.h"
#include "xinput_pad.h"
#define CONTROL_BUTTONS 14
#define CONTROL_DEADZONE_MAX 9500
#define CONTROL_GAMMA_MIN 100
#define CONTROL_GAMMA_MAX 400
/* Deadzones are fractions /10000; gamma is /100. Invert bit0=X, bit1=Y. */
typedef struct { uint16_t deadzone,gamma; uint8_t invert; } control_stick_t;
typedef struct { uint16_t deadzone,gamma; } control_trigger_t;
/* kind0: gamepad index; kind1: HID usage4..E7; kind2: disabled,target0. */
typedef struct { uint8_t kind,target; } control_binding_t;
typedef struct {
    control_stick_t sticks[2];
    control_trigger_t triggers[2];
    control_binding_t bindings[CONTROL_BUTTONS];
} control_profile_t;
void control_defaults(control_profile_t *profile);
bool control_profile_valid(const control_profile_t *profile);
control_profile_t *control_current(void);
void control_transform(const control_profile_t *profile,const xinput_pad_t *input,xinput_pad_t *output,uint8_t keyboard[8]);
/* true means this command was recognized, including a rejected value/state. */
bool control_console(pedal_t *pedal,const char *line,char out[CONSOLE_RESPONSE_SIZE]);
#endif
