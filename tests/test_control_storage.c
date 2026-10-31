#include "storage.h"
#include "control_record.h"
#include "config_record.h"
#include "hardware/flash.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
uint8_t fake_flash[2*1024*1024];
static size_t program_limit=256; static unsigned erases; static bool safe_failure;
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
    CHECK(timeout==1000); if(safe_failure) return -1; fn(ctx); return 0;
}
int main(void) {
    memset(fake_flash,0xff,sizeof(fake_flash)); pedal_config_t c,d;
    control_current()->sticks[0].gamma=250; storage_load(&c);
    CHECK(control_current()->sticks[0].gamma==100 && !c.axis[0].calibrated);
    c.axis[0].released=300; c.axis[0].pressed=3800; c.axis[0].calibrated=true;
    CHECK(config_encode(&c,42,fake_flash+sizeof(fake_flash)-8192));
    storage_load(&d); CHECK(d.axis[0].calibrated && d.axis[0].released==300 && control_current()->sticks[0].gamma==100);
    CHECK(erases==0); /* migration is RAM only until explicit SAVE */
    CHECK(storage_save(&d)); CHECK(erases==1 && memcmp(fake_flash+sizeof(fake_flash)-4096,"PDL2",4)==0);
    CHECK(storage_save(&d)); CHECK(erases==1);
    control_profile_t custom=*control_current(); custom.sticks[0]=(control_stick_t){1250,250,3};
    custom.triggers[1]=(control_trigger_t){500,300}; custom.bindings[10]=(control_binding_t){1,0xe1};
    for(size_t cut=0;cut<CONTROL_RECORD_SIZE;cut++) {
        *control_current()=custom; program_limit=cut; CHECK(!storage_save(&d));
        storage_load(&d); CHECK(d.axis[0].calibrated && d.axis[0].released==300 && control_current()->sticks[0].gamma==100);
    }
    *control_current()=custom; program_limit=256; CHECK(storage_save(&d));
    control_defaults(control_current()); storage_load(&c);
    CHECK(c.axis[0].calibrated && c.axis[0].pressed==3800 && memcmp(control_current(),&custom,sizeof(custom))==0);
    unsigned before=erases; CHECK(storage_save(&c) && before==erases);
    safe_failure=true; control_current()->triggers[0].gamma=400; CHECK(!storage_save(&c));
    safe_failure=false; storage_load(&d); CHECK(control_current()->triggers[0].gamma==100);
    fake_flash[sizeof(fake_flash)-8192+70]^=1; storage_load(&c);
    CHECK(c.axis[0].calibrated && control_current()->sticks[0].gamma==100); /* previous complete record */
    uint8_t record[CONTROL_RECORD_SIZE]; uint32_t seq=0; control_profile_t decoded;
    CHECK(control_record_encode(&c,&custom,0xffffffffu,record));
    CHECK(control_record_decode(record,sizeof(record),&d,&decoded,&seq) && seq==0xffffffffu);
    for(unsigned i=0;i<CONTROL_RECORD_SIZE;i++) {
        record[i]^=1; CHECK(!control_record_decode(record,sizeof(record),&d,&decoded,&seq)); record[i]^=1;
    }
    uint8_t newer[CONTROL_RECORD_SIZE]; CHECK(control_record_encode(&c,&custom,0,newer));
    CHECK(control_record_select(record,sizeof(record),newer,sizeof(newer),&d,&decoded,&seq)==1 && seq==0);
    CHECK(!control_record_decode(record,sizeof(record)-1,&d,&decoded,&seq));
    custom.bindings[0].kind=9; CHECK(!control_record_encode(&c,&custom,1,record));
    puts("PASS: unified HOST storage, legacy calibration migration, 256 torn writes, CRC, wrap and no-op"); return 0;
}
