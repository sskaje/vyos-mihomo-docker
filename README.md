
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
set container name clash allow-host-networks
set container name clash allow-host-pid
set container name clash capability 'net-admin'
set container name clash capability 'net-raw'
set container name clash device dev-net-tun destination '/dev/net/tun'
set container name clash device dev-net-tun source '/dev/net/tun'
set container name clash image 'docker.io/metacubex/mihomo:latest'
set container name clash label io.containers.autoupdate value 'registry'
set container name clash restart 'always'
set container name clash volume config destination '/root/.config/mihomo'
set container name clash volume config mode 'rw'
set container name clash volume config source '/config/clash/work'

# NAT
set nat source rule 1201 outbound-interface name utun0
set nat source rule 1201 translation address masquerade

# Firewall
set firewall zone WAN member interface utun0

commit
save
```


##### Container Mirror

You'll need VyOS >= [nightly 2025-03-13](https://vyos.net/get/nightly-builds/). 

```
# podman pull 192.168.1.10:8088/metacubex/mihomo:latest
set container registry 192.168.1.10:8088 insecure


# podman pull docker.io/metacubex/mihomo:latest
set container registry docker.io insecure
set container registry docker.io mirror address '192.168.1.10'
set container registry docker.io mirror port '8088'

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

Policy Based Routing

Using TUN only.

``` 
# Client IPs
set firewall group address-group SRC_CLASH address '192.168.1.20'

# To Match Route DNS Service
set firewall group address-group ROUTER_IN address '192.168.1.1'


# NAT for DNS Hijack
set nat destination rule 5000 description 'Clash UDP port'
set nat destination rule 5000 destination group address-group 'ROUTER_IN'
set nat destination rule 5000 destination port '53'
set nat destination rule 5000 protocol 'udp'
set nat destination rule 5000 source group address-group 'SRC_CLASH'
set nat destination rule 5000 translation port '7874'

# PBR, LAN Interface eth0
set policy route ROUTE_CLASH_TUN default-log
set policy route ROUTE_CLASH_TUN interface 'eth0'
set policy route ROUTE_CLASH_TUN rule 151 action 'accept'
set policy route ROUTE_CLASH_TUN rule 151 destination group network-group 'CHINA_IP'
set policy route ROUTE_CLASH_TUN rule 1000 set table '18'
set policy route ROUTE_CLASH_TUN rule 1000 source group address-group 'SRC_CLASH'

# Route table
set protocols static table 18 route 0.0.0.0/0 next-hop 198.18.0.1 interface 'utun0'
# default route table for all fake-ip 
set protocols static route 198.18.0.0/15 interface utun0
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