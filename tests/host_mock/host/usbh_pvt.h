typedef struct {
    const char *name;
    bool (*init)(void);
    bool (*open)(uint8_t port,uint8_t addr,const tusb_desc_interface_t *,uint16_t size);
    bool (*set_config)(uint8_t addr,uint8_t itf);
    bool (*xfer_cb)(uint8_t addr,uint8_t ep,xfer_result_t result,uint32_t size);
    void (*close)(uint8_t addr);
} usbh_class_driver_t;
bool usbh_edpt_busy(uint8_t addr,uint8_t ep);
bool usbh_edpt_claim(uint8_t addr,uint8_t ep);
void usbh_edpt_release(uint8_t addr,uint8_t ep);
bool usbh_edpt_xfer(uint8_t addr,uint8_t ep,uint8_t *buffer,uint16_t size);
void usbh_driver_set_config_complete(uint8_t addr,uint8_t itf);
