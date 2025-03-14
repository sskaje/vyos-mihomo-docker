
# Clash Control for VyOS (Container)


### Host Network + Tun Mode

#### Config File

/config/clash/work/overwrite/99-tun.yaml

``` 
tun:
  device: utun0
  auto-route: false
  auto-detect-interface: false
  enable: true
  stack: system
```


#### Create Container
``` 
configure
set container name clash image 'docker.io/metacubex/mihomo:Alpha'
set container name clash label io.containers.autoupdate value 'registry'
set container name clash volume config destination '/root/.config/mihomo'
set container name clash volume config mode 'rw'
set container name clash volume config source '/config/clash/work'

set container name clash capability net-admin
set container name clash capability net-raw
set container name clash device dev-net-tun source /dev/net/tun
set container name clash device dev-net-tun destination /dev/net/tun

# NAT
set nat source rule 1201 outbound-interface name utun0
set nat source rule 1201 translation address masquerade

# Firewall
set firewall zone WAN member interface utun0

commit
save
```



#### Create Rule

Static Route
``` 
# direct route entry
set protocols static route 8.8.0.0/16 interface utun0
# fake ip mode
set protocols static route 198.18.0.0/16 interface utun0
```

Static Route Table

``` 
set protocols static table 20 route 8.8.0.0/16 interface utun0

```



### MacVLAN + Any Mode

not tested yet

#### Create Container
``` 
configure
set container name clash image 'docker.io/metacubex/mihomo:Alpha'
set container name clash label io.containers.autoupdate value 'registry'
set container name clash volume config destination '/root/.config/mihomo'
set container name clash volume config mode 'rw'
set container name clash volume config source '/config/clash/work'
commit
save
```


#### Create Rule





## Update 

``` 
configure
set system task-scheduler task update-clash-config executable path

commit
save
```