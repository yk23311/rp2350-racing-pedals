#include <stdint.h>
extern uint8_t fake_flash[2*1024*1024];
#define XIP_BASE ((uintptr_t)fake_flash)
