#ifndef CONSOLE_H
#define CONSOLE_H
#include "pedal.h"
#include <stddef.h>
#define CONSOLE_LINE_SIZE 128
#define CONSOLE_RESPONSE_SIZE 768
typedef bool (*console_save_fn)(void *context,const pedal_config_t *config);
typedef struct {
    char line[CONSOLE_LINE_SIZE];
    size_t used;
    bool overflow;
} console_input_t;
void console_execute(pedal_t *pedal,const char *line,console_save_fn save,void *context,char response[CONSOLE_RESPONSE_SIZE]);
bool console_feed(console_input_t *input,char ch,pedal_t *pedal,console_save_fn save,void *context,char response[CONSOLE_RESPONSE_SIZE]);
#endif
