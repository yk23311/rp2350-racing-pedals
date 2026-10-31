#include "control_profile.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
int main(void) {
    pedal_config_t c; pedal_t p; pedal_defaults(&c); pedal_init(&p,&c);
    uint16_t raw[2]={0,0}; pedal_sample(&p,raw); CHECK(p.armed);
    char out[CONSOLE_RESPONSE_SIZE]; control_defaults(control_current());
    console_execute(&p,"PROFILE",NULL,NULL,out); CHECK(strncmp(out,"OK {",4)==0 && strstr(out,"\"bindings\":[[0,0],[0,1]"));
    CHECK(strlen(out)<CONSOLE_RESPONSE_SIZE-1); uint32_t generation=p.generation;
    console_execute(&p,"STICK 0 2000 200 3",NULL,NULL,out); CHECK(strcmp(out,"OK\n")==0 && !p.armed && p.generation==generation+1);
    CHECK(control_current()->sticks[0].gamma==200);
    console_execute(&p,"TRIGGER 1 500 300",NULL,NULL,out); CHECK(strcmp(out,"OK\n")==0 && control_current()->triggers[1].gamma==300);
    console_execute(&p,"BIND 13 1 225",NULL,NULL,out); CHECK(strcmp(out,"OK\n")==0 && control_current()->bindings[13].target==225);
    const char *bad[]={"STICK 2 0 100 0","STICK 0 9501 100 0","STICK 0 0 99 0","STICK 0 0 401 0","STICK 0 0 100 4","TRIGGER 0 -1 100","BIND 14 0 0","BIND 0 0 14","BIND 0 1 0","BIND 0 2 1","BIND 0 257 4","BIND 0 1 999999999999999999999999999","PROFILE extra"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {
        control_profile_t before=*control_current(); generation=p.generation;
        console_execute(&p,bad[i],NULL,NULL,out); CHECK(strncmp(out,"ERR",3)==0);
        CHECK(memcmp(&before,control_current(),sizeof(before))==0 && generation==p.generation);
    }
    CHECK(pedal_cal_begin(&p,0)); control_profile_t before=*control_current();
    console_execute(&p,"BIND 0 2 0",NULL,NULL,out); CHECK(strncmp(out,"ERR",3)==0 && memcmp(&before,control_current(),sizeof(before))==0);
    puts("PASS: bounded control protocol, atomic validation and mutation reset"); return 0;
}
