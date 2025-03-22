
# Clash Control for VyOS (Container)

## Install

Install to /config/clash

```
wget https://github.com/sskaje/vyos-mihomo-docker/archive/refs/heads/main.tar.gz
mkdir tmp && tar -C tmp -xvf main.tar.gz --strip=1
mv tmp/config/clash /config/
mv tmp/bin/* /config/clash/bin/

```

Edit `/config/clash/clash.yaml` to use your subscription. Make sure to container matches your config tree entry.



## Configurations


### Host Network + Tun Mode

**DON'T USE `utun0` on VyOS, USE `tun0` !!**

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
set container name mihomo allow-host-networks
set container name mihomo allow-host-pid
set container name mihomo capability 'net-admin'
set container name mihomo capability 'net-raw'
set container name mihomo device dev-net-tun destination '/dev/net/tun'
set container name mihomo device dev-net-tun source '/dev/net/tun'
set container name mihomo image 'docker.io/metacubex/mihomo:latest'
set container name mihomo label io.containers.autoupdate value 'registry'
set container name mihomo restart 'always'
set container name mihomo volume config destination '/root/.config/mihomo'
set container name mihomo volume config mode 'rw'
set container name mihomo volume config source '/config/clash/work'

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
set protocols static route 8.8.0.0/16 interface tun0
# fake ip mode
set protocols static route 198.18.0.0/16 interface tun0
```

Static Route Table

``` 
set protocols static table 20 route 8.8.0.0/16 interface tun0

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
set protocols static table 18 route 0.0.0.0/0 interface 'tun0'
# default route table for all fake-ip 
set protocols static route 198.18.0.0/15 interface tun0
```


### Local traffic

Wait for https://github.com/vyos/vyos-1x/pull/4391 

Or

``` 
sudo nft add chain ip vyos_nat OUTPUT { type nat hook output priority -100 \; }

sudo nft add rule ip vyos_nat OUTPUT ip daddr 127.0.0.1 tcp dport 53 dnat to 127.0.0.1:7874
sudo nft add rule ip vyos_nat OUTPUT ip daddr 127.0.0.1 udp dport 53 dnat to 127.0.0.1:7874

```

## Update Config 

### Manually generate

`/config/clash/bin/clashctl.py generate_config`

### Manually reload

`/config/clash/bin/clashctl.py reload`

### Restart container

Match your container name!

`restart container mihomo`

### Use task scheduler

``` 
configure
set system task-scheduler task update-mihomo-config executable path /config/clash/bin/clashctl.py
set system task-scheduler task update-mihomo-config executable arguments rehash
# 04:20 am everyday
set system task-scheduler task update-mihomo-config crontab-spec "20 4 * * *"
commit
save
```

## Custom config

Keep your custom config files prefixed by a fixed width number, like 00-99.  

Entries not named 'rules', load by name order. Entries named 'rules', last insert comes first.

Check examples under 99-rules, 99-test.yaml will be the first rule, 01-myadblock.yaml will be second, rest from subscription files will be last.

For other entries, config from subscription file always comes as first.


### Syntax

`!replace` and `!delete` is supported to replace / delete whole entry

Example: 

``` 
dns:
  direct-nameserver:
  - 119.29.29.29
  - 114.114.114.114
```

\+ 
```
root@vyos-rt:/config/clash/utun/overwrite# cat 89-dns-system.yaml
dns:
  direct-nameserver: !replace
  - system
```

Will get `direct-nameserver` replaced.

If with 
``` 
dns:
  direct-nameserver:
  - 1.1.1.1
```
Will get
``` 
dns:
  direct-nameserver:
  - 119.29.29.29
  - 114.114.114.114
  - 1.1.1.1
```
