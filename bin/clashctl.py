#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import MutableMapping
import requests
from pathlib import Path
import yaml


class YAMLConfigMerger:
    """
    用于加载、处理和合并 YAML 配置文件，支持替换和删除操作
    支持语法 !replace 和 !delete
    """
    def __init__(self):
        # 注册 YAML 自定义标签
        self._register_yaml_tags()

    def _register_yaml_tags(self):
        """注册 !replace 和 !delete 标签解析器"""
        yaml.SafeLoader.add_constructor('!replace', self._replace_constructor)
        yaml.SafeLoader.add_constructor('!delete', self._delete_constructor)

    def _replace_constructor(self, loader, node):
        """处理 !replace 标签，用于字典和列表的替换"""
        if isinstance(node, yaml.MappingNode):
            return self.ReplaceTag(loader.construct_mapping(node))
        elif isinstance(node, yaml.SequenceNode):
            return self.ReplaceTag(loader.construct_sequence(node))
        else:
            return loader.construct_scalar(node)

    def _delete_constructor(self, loader, node):
        """处理 !delete 标签，用于删除字典或列表中的项"""
        return self.DeleteTag()

    def deep_merge(self, source, destination):
        """
        深度合并两个字典，支持 !replace 和 !delete 语法
        """
        for key, value in source.items():
            if isinstance(value, self.ReplaceTag):
                destination[key] = value.value
            elif isinstance(value, self.DeleteTag):
                if key in destination:
                    del destination[key]
            elif isinstance(value, MutableMapping):
                node = destination.setdefault(key, {})
                self.deep_merge(value, node)
            elif isinstance(value, list):
                if key in destination and isinstance(destination[key], list):
                    if key == 'rules':
                        destination[key] = value + destination[key]
                    else:
                        destination[key] = destination[key] + value
                else:
                    destination[key] = value
            else:
                destination[key] = value
        return destination

    def load_yaml(self, yaml_content):
        """加载 YAML 内容并返回字典"""
        return yaml.load(yaml_content, Loader=yaml.SafeLoader)

    def dump_yaml(self, data):
        """将字典数据转换为 YAML 格式"""
        return yaml.dump(data, allow_unicode=True)

    class ReplaceTag:
        """标记 !replace 语法，用于复杂结构的替换"""
        def __init__(self, value):
            self.value = value

    class DeleteTag:
        """标记 !delete 语法，用于删除字典或列表中的项"""
        def __init__(self, value=None):
            self.value = value


class ClashControlConfig:

    def __init__(self, config_path):
        with open(config_path) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)

    def get_container_command(self):
        return self.config.get('container', {}).get('command', 'podman')

    def get_container_image(self):
        return self.config.get('container', {}).get('image', 'docker.io/metacubex/mihomo:latest')

    def get_container_workdir(self):
        return self.config.get('container', {}).get('workdir', '/root/.config/mihomo/')

    def get_instance_name(self):
        return self.config.get('instance', {}).get('name')

    def get_subscription_url(self):
        return self.config.get('instance', {}).get('subscription')

    def get_clash_root(self):
        return self.config.get('instance', {}).get('clash_root')

    def get_providers(self, type_filter=None):
        if type_filter is None:
            return self.config.get('providers', [])
        else:
            return [x for x in self.config.get('providers', []) if x.get('provider-type', '') == type_filter]


class ClashControl:

    clash_root = '/config/clash'

    clash_config = clash_root + '/clash.yaml'

    subscription_file = 'config.yaml'

    dashboard_repo_ids = [
        "MetaCubeX/metacubexd",
        "haishanh/yacd",
        "ayanamist/clash-dashboard",
        'Zephyruso/zashboard'
    ]

    config_test_dir = '/tmp/clash-config-test'

    def ensure_dir(self, dirs):
        for dirname in dirs:
            os.makedirs(dirname, exist_ok=True)

    def __init__(self):
        self.config = ClashControlConfig(self.clash_config)
        self.config_dir = self.config.get_clash_root()
        self.ui_dir = self.config_dir + '/ui'

        self.ensure_dir([
            self.config_dir,
            self.ui_dir,
            os.path.join(self.config_dir, 'overwrite'),
            os.path.join(self.config_dir, 'download'),
        ])

        self.latest_config_symlink = os.path.join(self.config_dir, 'download', "latest_config.yaml")

    def install_ui(self):
        for repo_id in self.dashboard_repo_ids:
            dashboard_url = f'https://github.com/{repo_id}/archive/refs/heads/gh-pages.tar.gz'

            name = os.path.basename(repo_id)
            with requests.get(dashboard_url, allow_redirects=True) as response:
                response.raise_for_status()

                with tempfile.NamedTemporaryFile() as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # 忽略空块
                            temp_file.write(chunk)

                    temp_file.flush()

                    os.makedirs(f"{self.ui_dir}/{name}", exist_ok=True)
                    subprocess.run(
                        ['tar', '--strip-components=1', '-xv', '-C', f"{self.ui_dir}/{name}", '-f', temp_file.name],
                        check=True)

    def require_container(self):
        pass

    def get_container_run_command(self, extra_args=None):
        if extra_args:
            return [self.config.get_container_command(), 'run', '--rm'] + extra_args + [self.config.get_container_image()]

        return [self.config.get_container_command(), 'run', '--rm', self.config.get_container_image()]

    def get_container_op_command(self, command, extra_args=None):
        if extra_args:
            return [self.config.get_container_command(), command] + extra_args

        return [self.config.get_container_command(), command]

    def run_command(self, command):
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

    def run_container_op_command(self, command, extra_args=None):
        command = self.get_container_op_command(command, extra_args)
        print(self.run_command(command).stdout)

    def download_subscription(self):

        # /config/clash/utun/ for clash configs
        # parse yaml
        subscription_url = self.config.get_subscription_url()

        resp = requests.get(subscription_url)
        if resp.status_code != 200:
            raise Exception('Subscription download failed')

        os.makedirs(self.config_test_dir, exist_ok=True)

        with tempfile.NamedTemporaryFile(dir=self.config_test_dir) as temp_file:
            temp_file.write(resp.content)
            temp_file.flush()

            if os.path.exists(self.latest_config_symlink):
                with open(self.latest_config_symlink, 'rb') as r:
                    if r.read() == resp.content:
                        print('Subscription not changed.')
                        return self.latest_config_symlink

            result = subprocess.run(
                self.get_container_run_command([
                    '-v', f'{self.config_test_dir}:{self.config_test_dir}',
                    '--network', 'host',
                ]) + [
                    '-d', self.config_test_dir, '-f', temp_file.name, '-t'],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception('Unable to verify subscription: Command execution failed')

            if result.stdout.find('Initial configuration complete') > -1 and \
                    result.stdout.find('test is successful') > -1:
                print('Successfully verified subscription')

                timestamp = time.strftime("%Y%m%d_%H%M%S")
                versioned_config_name = f"config_{timestamp}.yaml"
                versioned_config_path = os.path.join(self.config_dir, 'download', versioned_config_name)

                shutil.copy(temp_file.name, versioned_config_path)

                if os.path.exists(self.latest_config_symlink) or os.path.islink(self.latest_config_symlink):
                    os.remove(self.latest_config_symlink)

                os.symlink(versioned_config_path, self.latest_config_symlink)

                return versioned_config_path
            else:
                raise Exception('Unable to verify subscription: Verification failed')

    def load_yaml_files(self, downloaded_file, merge_directory):
        config_merger = YAMLConfigMerger()

        merged_config = {}
        # 加载所有 YAML 文件的内容
        with open(downloaded_file, 'r') as f:
            merged_config = config_merger.load_yaml(f)

        # add to proxy-groups / * / use
        for provider in self.config.get_providers('proxy-providers'):
            del provider['provider-type']

            if 'add-provider-to-proxy-group' in provider and 'proxy-groups' in merged_config:
                for i in range(len(merged_config['proxy-groups'])):
                    proxy_group = merged_config['proxy-groups'][i]
                    for add_group in provider['add-provider-to-proxy-group']:
                        if proxy_group['name'].strip() == add_group.strip():
                            merged_config['proxy-groups'][i]['use'].append(provider['name'])
                            break
                del provider['add-provider-to-proxy-group']

            if 'create-proxy-group' in provider:
                provider['create-proxy-group']['use'] = [provider['name']]
                merged_config['proxy-groups'].append(provider['create-proxy-group'])

                if 'add-proxies-to-proxy-group' in provider:
                    for i in range(len(merged_config['proxy-groups'])):
                        proxy_group = merged_config['proxy-groups'][i]
                        for add_group in provider['add-proxies-to-proxy-group']:
                            if proxy_group['name'].strip() == add_group.strip():
                                merged_config['proxy-groups'][i]['proxies'].append(provider['create-proxy-group']['name'])
                                if provider['name'] not in merged_config['proxy-groups'][i]['use']:
                                    merged_config['proxy-groups'][i]['use'].append(provider['name'])
                                break

                    del provider['add-proxies-to-proxy-group']

                del provider['create-proxy-group']

            merged_config['proxy-providers'][provider['name']] = provider

        if os.path.exists(merge_directory):
            # 获取目录下所有的 YAML 文件
            yaml_files = sorted(Path(merge_directory).rglob('*.yaml'), key=lambda p: str(p))

            for file in yaml_files:
                with open(file, 'r') as f:
                    config = yaml.safe_load(f)
                    if config is not None:
                        merged_config = config_merger.deep_merge(config, merged_config)

        return merged_config

    def reload_config(self):
        """ curl --location --request PUT 'http://localhost:9090/configs' \
--header 'Content-Type: application/json' \
--data-raw '{"path": "/root/.config/clash/config.yaml"}'
"""

        with open(os.path.join(self.config_dir, self.subscription_file), 'r') as f:
            cfg = yaml.safe_load(f)

            if 'external-controller' not in cfg:
                raise Exception('Missing external controller')

            _, port = cfg['external-controller'].split(':')

            url = f"http://localhost:{port}/configs"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg['secret']}"
            }
            data = {
                "path": "/root/.config/mihomo/config.yaml"
            }

            response = requests.put(url, json=data, headers=headers)

            print(response.text)

    def generate_config(self, downloaded_file):
        with open(os.path.join(self.config_dir, self.subscription_file), 'w') as f:
            yaml.dump(self.load_yaml_files(downloaded_file, os.path.join(self.config_dir, 'overwrite')), f, default_flow_style=False)

    def cmd_restart(self):
        command = ['systemctl', 'restart', f'vyos-container-{self.config.get_instance_name()}.service']
        print(self.run_command(command).stdout)

    def cmd_stop(self):
        command = ['systemctl', 'stop', f'vyos-container-{self.config.get_instance_name()}.service']
        print(self.run_command(command).stdout)

    def cmd_status(self):
        self.run_container_op_command('ps')

    def cmd_reload(self):
        self.reload_config()

    def cmd_install_ui(self):
        self.install_ui()

    def cmd_show_ui(self):
        pass

        # read yaml
        # get port, allow-lan, auth


def main():
    parser = argparse.ArgumentParser(
        description="Clashctl for VyOS by sskaje",
        epilog="DEV is the device name (e.g., utun0).",
        # usage="python %(prog)s COMMAND [args] [options]"
    )

    subparsers = parser.add_subparsers(dest="command", metavar='COMMAND')

    subparsers.add_parser("stop", help="Stop")
    subparsers.add_parser("restart", help="Restart")
    subparsers.add_parser("status", help="Show instance status")
    subparsers.add_parser("rehash", help="Download config and restart to reload")
    subparsers.add_parser("reload", help="Reload config")
    subparsers.add_parser("generate_config", help="Generate instance configuration")
    subparsers.add_parser("purge_cache", help="Remove cache.db and restart")
    # subparsers.add_parser("install", help="Install")
    subparsers.add_parser("update_ui", help="Download Dashboard UI")
    subparsers.add_parser("show_ui", help="Show Dashboard UI URL")
    subparsers.add_parser("help", help="Show this message")

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
    elif args.command is None:
        parser.print_usage()
    else:

        ctrl = ClashControl()
        if args.command == "stop":
            ctrl.cmd_stop()
        elif args.command == "restart":
            ctrl.cmd_restart()
        elif args.command == "status":
            ctrl.cmd_status()
        elif args.command == "reload":
            ctrl.cmd_reload()
        elif args.command == "rehash":
            downloaded_name = ctrl.download_subscription()
            ctrl.generate_config(downloaded_name)
            ctrl.cmd_reload()
        elif args.command == "generate_config":
            downloaded_name = ctrl.latest_config_symlink
            ctrl.generate_config(downloaded_name)
        elif args.command == "update_ui":
            ctrl.cmd_install_ui()
        elif args.command == "show_ui":
            ctrl.cmd_show_ui()
        else:
            print('Unknown command')


if __name__ == "__main__":
    main()

