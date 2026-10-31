#include "console.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static bool save(void *ctx,const pedal_config_t *c) { CHECK(pedal_config_valid(c)); (*(int*)ctx)++; return true; }
int main(void) {
    pedal_config_t c; pedal_t p; char out[CONSOLE_RESPONSE_SIZE]; int saved=0;
    pedal_defaults(&c); pedal_init(&p,&c); uint16_t raw[2]={0,0}; pedal_sample(&p,raw);
    console_execute(&p,"GET",save,&saved,out); CHECK(strncmp(out,"OK {",4)==0 && strstr(out,"\"raw\":[0,0]"));
    console_execute(&p,"PING 0123456789abcdef0123456789abcdef",save,&saved,out);
    CHECK(strcmp(out,"OK {\"sync\":\"0123456789abcdef0123456789abcdef\"}\n")==0);
    console_execute(&p,"PING not-a-valid-token",save,&saved,out); CHECK(strncmp(out,"ERR",3)==0);
    console_execute(&p,"SET 0 400 100 150 2",save,&saved,out); CHECK(strcmp(out,"OK\n")==0 && p.config.axis[0].gamma==150);
    const char *bad[]={"SET 0 100 400 150 2","SET 2 400 100 150 2","SET 0 -1 0 100 1","SET 0 400 100 nan 2","SET 0 400 100 999999999999999999 2","SET 0 400 100 150 2 tail","GET junk","MODE BAD","CAL 0 END","SET 0 400 100 150 0"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++) { c=p.config; console_execute(&p,bad[i],save,&saved,out); CHECK(strncmp(out,"ERR",3)==0); CHECK(memcmp(&c,&p.config,sizeof(c))==0); }
    console_execute(&p,"SAVE",save,&saved,out); CHECK(strncmp(out,"ERR",3)==0 && saved==0); /* disarmed after SET */
    pedal_sample(&p,raw); console_execute(&p,"SAVE",save,&saved,out); CHECK(saved==1);
    console_execute(&p,"CAL 0 BEGIN",save,&saved,out); CHECK(strcmp(out,"OK\n")==0);
    console_execute(&p,"SET 0 400 100 200 2",save,&saved,out); CHECK(strncmp(out,"ERR",3)==0);
    console_execute(&p,"SAVE",save,&saved,out); CHECK(saved==1);
    console_execute(&p,"CAL 1 CANCEL",save,&saved,out); CHECK(strncmp(out,"ERR",3)==0);
    console_execute(&p,"CAL 0 CANCEL",save,&saved,out); CHECK(p.calibration_axis==-1);
    console_execute(&p,"MODE KEYBOARD",save,&saved,out); CHECK(p.mode==PEDAL_KEYBOARD);
    console_input_t input={0};
    for(int i=0;i<200;i++) CHECK(!console_feed(&input,'A',&p,save,&saved,out));
    CHECK(console_feed(&input,'\n',&p,save,&saved,out) && strstr(out,"TOO_LONG"));
    CHECK(!console_feed(&input,'G',&p,save,&saved,out)); CHECK(!console_feed(&input,'E',&p,save,&saved,out));
    CHECK(!console_feed(&input,'T',&p,save,&saved,out)); CHECK(!console_feed(&input,'\r',&p,save,&saved,out));
    CHECK(console_feed(&input,'\n',&p,save,&saved,out) && strncmp(out,"OK {",4)==0);
    puts("PASS: console validation, atomic update, calibration, save gating, line recovery"); return 0;
}
