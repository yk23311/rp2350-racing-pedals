#include "report_gate.h"
void report_gate_reset(report_gate_t *g) {
    g->epoch++;
    for(unsigned i=0;i<2;i++) { g->pending[i]=true; g->last_neutral[i]=false; }
}
bool report_gate_blocked(const report_gate_t *g) { return g->pending[0] || g->pending[1]; }
bool report_gate_begin(report_gate_t *g,unsigned i,bool neutral) {
    if(i>=2 || g->busy[i] || (!neutral && report_gate_blocked(g))) return false;
    g->busy[i]=true; g->sent_epoch[i]=g->epoch; g->sent_neutral[i]=neutral; return true;
}
void report_gate_complete(report_gate_t *g,unsigned i) {
    if(i>=2 || !g->busy[i]) return;
    g->busy[i]=false;
    if(g->sent_epoch[i]!=g->epoch) return;
    g->last_neutral[i]=g->sent_neutral[i];
    if(g->sent_neutral[i]) g->pending[i]=false;
}
bool report_gate_quiet(const report_gate_t *g) {
    return !report_gate_blocked(g) && !g->busy[0] && !g->busy[1] && g->last_neutral[0] && g->last_neutral[1];
}
