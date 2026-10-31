#include "storage.h"
#include "hardware/flash.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while(0)
uint8_t fake_flash[2*1024*1024];
static size_t program_limit=256;
static unsigned erases;
static bool safe_failure;
void flash_range_erase(uint32_t offset,size_t count) {
    CHECK(offset>=sizeof(fake_flash)-8192 && offset%4096==0 && count==4096);
    memset(fake_flash+offset,0xff,count); erases++;
}
void flash_range_program(uint32_t offset,const uint8_t *data,size_t count) {
    CHECK(offset>=sizeof(fake_flash)-8192 && offset%256==0 && count==256);
    size_t n=program_limit<count?program_limit:count;
    for(size_t i=0;i<n;i++) { CHECK((fake_flash[offset+i]&data[i])==data[i]); fake_flash[offset+i]&=data[i]; }
}
int flash_safe_execute(void (*fn)(void *),void *ctx,unsigned timeout) {
    CHECK(timeout==1000); if(safe_failure) return -1; fn(ctx);return 0;
}
int main(void) {
    memset(fake_flash,0xff,sizeof(fake_flash));
    pedal_config_t c,d; storage_load(&c); CHECK(!c.axis[0].calibrated);
    CHECK(storage_save(&c)); CHECK(erases==1);
    CHECK(storage_save(&c)); CHECK(erases==1); /* no-op avoids wear */
    c.axis[0].gamma=150;
    for(size_t cut=0;cut<40;cut++) {
        program_limit=cut; CHECK(!storage_save(&c));
        storage_load(&d); CHECK(d.axis[0].gamma==100); /* reboot chooses old valid slot */
    }
    program_limit=256; CHECK(storage_save(&c)); storage_load(&d); CHECK(d.axis[0].gamma==150);
    safe_failure=true; c.axis[0].gamma=200; CHECK(!storage_save(&c));
    storage_load(&d); CHECK(d.axis[0].gamma==150);
    safe_failure=false;
    fake_flash[sizeof(fake_flash)-4096+20]^=1;
    storage_load(&d); CHECK(d.axis[0].gamma==100);
    puts("PASS: actual storage adapter, torn writes at 40 offsets, fallback, no-op, failure");return 0;
}
