# SwitchMap وضعیت نهایی Phase109-R16

تاریخ وضعیت: 2026-06-29 شب
مسیر پروژه: `C:\SwitchMap`
آدرس سایت: `http://it-tools.winac-co.com:8000/`

## وضعیت سالم فعلی

- Search در Dashboard سالم است.
- مشکل Cache / Static قدیمی بعد از R9/R10 و Static Sync رفع شد.
- موارد `LLDP-62`، `rb2011`، `192.168.101.10` در جستجو پیدا می‌شوند.
- `LLDP-0` خراب وجود ندارد.
- توپولوژی اصلی NEXUS / Edari / Salon سالم است.
- `reciprocal_missing_count=0` شده است.
- ۵ سوییچ Salon به Inventory اضافه و Poll/Discovery شدند.

## آمار نهایی Audit R16

```text
switch_count=24
active_switch_count=24
port_count=684
neighbor_port_count=88
network_neighbor_matched_count=33
endpoint_or_unmanaged_neighbor_count=51
unresolved_network_target_count=4
reciprocal_ok_count=33
reciprocal_missing_count=0
lldp_placeholder_ports=3
bad_lldp_0_ports=0
```

## سوییچ‌های Salon اضافه‌شده

```text
Salon-Gharbi           172.20.1.2   Cisco WS-C3850-48P   ports=52
Salon-jonobi           172.20.1.3   Cisco WS-C3850-48P   ports=52
Salon-Sharghi-PATROL   172.20.1.4   Cisco WS-C3850-48P   ports=52
Salon-Shomali          172.20.1.5   Cisco WS-C3850-48P   ports=52
Salon-Edari-Fiber      172.20.1.18  Cisco WS-C3850-12XS  ports=4
```

## لینک‌های اصلی NEXUS به Salon

```text
NEXUS Eth1/34 -> Salon-Sharghi-PATROL 172.20.1.4
NEXUS Eth1/35 -> Salon-jonobi 172.20.1.3
NEXUS Eth1/36 -> Salon-Edari-Fiber 172.20.1.18
NEXUS Eth1/37 -> Salon-Gharbi 172.20.1.2
NEXUS Eth1/39 -> Salon-Shomali 172.20.1.5
```

## تصمیم‌های اعمال‌شده

```text
RB-Edgge-Factory -> Hex-S alias/typo
RB-Audience-Wifi -> UNMANAGED_WIFI_EDGE
RB-1000 -> EXTERNAL_ISP_ROUTER_EDGE
```

## موارد باقی‌مانده برای R17

```text
1) AliHome ether2 -> ip=192.168.2.250
   تصمیم: Client / DHCP Endpoint
   اقدام R17: به‌عنوان Network Neighbor خطادار حساب نشود.

2) RB2011-Iranmall ether1 -> 7o8-Iranmall-EDGE / 172.16.1.1
   تصمیم: Pending Review
   اقدام R17: فعلاً دست نخورد؛ در گزارش Pending بماند.

3) Salon-Gharbi Te1/1/1 -> Salon-tolid.winac-co.com
   تصمیم: Production Fiber Switch / Pending Config
   توضیح: سوییچ فیبر سالن تولید است؛ خط Backup سوییچ‌های سالن تولید به آن وصل است؛ سه لینک به Salon-Edari-Fiber دارد؛ هنوز کانفیگ کامل نشده.
   اقدام R17: Pending Network Device، نه خطای توپولوژی.

4) Salon-Sharghi-PATROL Gi1/0/37 -> RB-CAP-Patrol
   تصمیم: Access Point واحد نگهبانی
   اقدام R17: Unmanaged AP / Endpoint حساب شود، نه Switch.
```

## قفل‌های کاری

```text
- هیچ Rollback لازم نیست.
- Discovery کلی اجرا نشود.
- DB قبل از هر Apply بکاپ شود.
- R17 فقط Classification همین ۴ مورد باشد.
- R17 نباید Search، Dashboard UI، SNMP Poll اصلی، یا Topology اصلی NEXUS/Edari/Salon را تغییر دهد.
- رمزها و Community ها در گزارش‌ها و Prompt ها ذخیره نشوند.
```
