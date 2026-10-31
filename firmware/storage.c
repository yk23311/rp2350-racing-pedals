#include "storage.h"
#include "config_record.h"
#if PEDAL_USB_HOST
#include "control_record.h"
#define STORE_RECORD_SIZE CONTROL_RECORD_SIZE
#else
#define STORE_RECORD_SIZE CONFIG_RECORD_SIZE
#endif
#include "hardware/flash.h"
#include "hardware/regs/addressmap.h"
#include "pico/flash.h"
#include "pico/stdlib.h"
#include <string.h>
#define STORE_OFFSET (2u*1024u*1024u-2u*FLASH_SECTOR_SIZE)
_Static_assert(PICO_FLASH_SIZE_BYTES==2*1024*1024,"This layout requires Waveshare's 2 MiB flash");
static int active_slot=-1;
static uint32_t sequence;
static const uint8_t *slot(unsigned i) { return (const uint8_t *)(XIP_BASE+STORE_OFFSET+i*FLASH_SECTOR_SIZE); }
void storage_load(pedal_config_t *config) {
#if PEDAL_USB_HOST
    active_slot=control_record_select(slot(0),STORE_RECORD_SIZE,slot(1),STORE_RECORD_SIZE,config,control_current(),&sequence);
    if(active_slot<0) { pedal_defaults(config); control_defaults(control_current()); sequence=0; }
#else
    active_slot=config_select(slot(0),CONFIG_RECORD_SIZE,slot(1),CONFIG_RECORD_SIZE,config,&sequence);
    if(active_slot<0) { pedal_defaults(config); sequence=0; }
#endif
}
typedef struct { uint32_t offset; uint8_t page[FLASH_PAGE_SIZE]; } write_job_t;
static void __not_in_flash_func(write_slot)(void *parameter) {
    write_job_t *job=parameter;
    flash_range_erase(job->offset,FLASH_SECTOR_SIZE);
    flash_range_program(job->offset,job->page,FLASH_PAGE_SIZE);
}
bool storage_save(const pedal_config_t *config) {
    if(!pedal_config_valid(config)) return false;
    uint8_t current[STORE_RECORD_SIZE];
#if PEDAL_USB_HOST
    if(!control_profile_valid(control_current())) return false;
    if(active_slot>=0 && control_record_encode(config,control_current(),sequence,current) &&
       memcmp(current,slot((unsigned)active_slot),sizeof(current))==0) return true;
#else
    if(active_slot>=0 && config_encode(config,sequence,current) &&
       memcmp(current,slot((unsigned)active_slot),sizeof(current))==0) return true;
#endif
    unsigned target=active_slot==0?1:0;
    write_job_t job; job.offset=STORE_OFFSET+target*FLASH_SECTOR_SIZE;
    memset(job.page,0xff,sizeof(job.page));
#if PEDAL_USB_HOST
    _Static_assert(CONTROL_RECORD_SIZE<=FLASH_PAGE_SIZE,"Control record must fit one flash page");
    if(!control_record_encode(config,control_current(),sequence+1,job.page)) return false;
#else
    if(!config_encode(config,sequence+1,job.page)) return false;
#endif
    if(flash_safe_execute(write_slot,&job,1000)!=PICO_OK) return false;
    if(memcmp(slot(target),job.page,STORE_RECORD_SIZE)!=0) return false;
    pedal_config_t verify; uint32_t new_sequence;
#if PEDAL_USB_HOST
    control_profile_t verify_profile;
    if(!control_record_decode(slot(target),STORE_RECORD_SIZE,&verify,&verify_profile,&new_sequence)) return false;
#else
    if(!config_decode(slot(target),CONFIG_RECORD_SIZE,&verify,&new_sequence)) return false;
#endif
    active_slot=(int)target; sequence=new_sequence; return true;
}
