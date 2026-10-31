#ifndef REPORT_GATE_H
#define REPORT_GATE_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    uint32_t epoch, sent_epoch[2];
    bool pending[2], busy[2], sent_neutral[2], last_neutral[2];
} report_gate_t;
void report_gate_reset(report_gate_t *gate);
bool report_gate_blocked(const report_gate_t *gate);
bool report_gate_begin(report_gate_t *gate,unsigned interface,bool neutral);
void report_gate_complete(report_gate_t *gate,unsigned interface);
bool report_gate_quiet(const report_gate_t *gate);
#endif
