# coding=utf-8
from mcdreforged.api.types import *
from mcdreforged.api.command import *
import re
import os
from typing import Any, List, Dict, Tuple
from mcdreforged.minecraft.rtext import RTextList, RColor, RAction, RText
from ruamel import yaml
from enum import Enum

yml = yaml.YAML()


waypoint_config_path = './config/waypoint.yaml'   # 路径点保存位置

help_msg = '''
======== §bWaypoints §r========
默认情况下有些指令需要 MCDR.helper 以上的权限, 具体可以使用 !!wp set_permission_level 进行修改
§b!!wp§r 显示本帮助信息
§b!!wp list§r 显示路径点列表
§b!!wp list <dim>§r 显示路径点列表
dim 可使用 1, 0, -1 代表末地，主世界，下界，或者直接使用 minecraft:the_end, minecraft:overworld, minecraft:the_nether
§b!!wp search <content>§r 搜索含有指定内容名字的路径点
§b!!wp add [name:name, x:1, y:2, z:3, dim:minecraft:overworld] §r 添加路径点（需要权限）
§b!!wp addvoxel§r 随后直接使用 voxel 分享一系列的路径点来添加路径点（需要权限）
§b!!wp addxaero§r 随后直接使用 voxel 分享一系列的路径点来添加路径点（需要权限）
§b!!wp del <content>§r 删除名字包含 <content> 的路径点，会有确认信息（需要权限）
§b!!wp set_world <world_name>§r 设置当前世界（为了适配 voxel 的多世界, 默认值为 '', 需要权限）
§b!!wp set_permission_level <permission_level>§r 设置权限（需要权限）
'''


PLUGIN_METADATA = {
    'id': 'waypoint',
    'version': '1.1.0',
    'name': 'waypoint',
    'description': 'waypoint',  # RText component is allowed
    'author': 'plusls',
    'link': 'https://github.com/plusls/MCDR-waypoint',
    'dependencies': {
            'mcdreforged': '>=1.0.0',
    }
}


@yml.register_class
class Waypoint:
    yaml_tag = '!Waypoint'
    dim_str_id_map = {
        "minecraft:overworld": 0,
        "minecraft:the_nether": -1,
        "minecraft:the_end": 1
    }

    dim_id_str_map = {
        0: "minecraft:overworld",
        -1: "minecraft:the_nether",
        1: "minecraft:the_end"
    }

    dim_id_rtext_map = {
        0: RText('主世界', color=RColor.green).h('minecraft:overworld'),
        -1: RText('下界', color=RColor.red).h('minecraft:the_nether'),
        1: RText('末地', color=RColor.dark_purple).h('minecraft:the_end'),
    }

    def __init__(self, name: str, x: str, y: str, z: str, dim: str):
        self.name = name
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.dim_id = self.get_dim_id(dim)
    
    @classmethod
    def get_dim_id_list(cls) -> List[int]:
        return list(cls.dim_id_str_map.keys())

    @classmethod
    def get_dim_id(cls, dim_str: str) -> int:
        return cls.dim_str_id_map[dim_str]

    @classmethod
    def get_dim_str(cls, dim_id: int) -> str:
        return cls.dim_id_str_map[dim_id]

    @classmethod
    def get_dim_rtext(cls, dim_id: int) -> RText:
        return cls.dim_id_rtext_map[dim_id]

    @staticmethod
    def check_result(result: dict) -> Dict[str, str]:
        ret = {}
        keys = ['name', 'x', 'y', 'z', 'dim']
        try:
            for key in keys:
                ret[key] = result[key]
        except KeyError:
            ret = {}
            pass
        return ret

    @classmethod
    def parse(cls, text: str) -> Tuple[ParseResult, str]:
        total_read = 0
        result = {}
        # 匹配 key value
        for match in re.finditer(r"[\[ ](.*?):(.*?)[\,\]]", text):
            result.setdefault(*match.groups())
            total_read = match.span()[1]
        if len(result) == 0:
            return ParseResult(None, total_read), '正则匹配失败'
        try:
            result = cls.check_result(result)
            if len(result) == 0:
                return ParseResult(None, total_read), '路径点缺少参数'
            waypoint = cls(**result)
        except KeyError:
            return ParseResult(None, total_read), '维度格式不正确'
        except ValueError:
            return ParseResult(None, total_read), '路径点坐标格式应为整数'
        return ParseResult(waypoint, total_read), ''

    XAERO_SHARE_STR = 'xaero-waypoint:'

    @classmethod
    def parse_xaero(cls, text: str) -> Tuple[ParseResult, str]:
        total_read = 0
        # xaero-waypoint:粘土山空置域:粘:-421:121:-5506:11:false:0:Internal-overworld-waypoints
        if not text.startswith(cls.XAERO_SHARE_STR):
            return ParseResult(None, total_read), 'xaero 分享格式不正确'

        total_read += len(cls.XAERO_SHARE_STR)
        text = text[len(cls.XAERO_SHARE_STR):]
        text_list = text.split(':')
        if len(text_list) != 9:
            return ParseResult(None, total_read), 'xaero 分享格式不正确'

        if not text_list[8].startswith('Internal-') or not text_list[8].endswith('-waypoints'):
            return ParseResult(None, total_read), 'xaero 维度格式不正确，应以 "Internal-" 开头 "-waypoints" 结束'
        text_list[8] = 'minecraft:' + text_list[8][len('Internal-'):-len('-waypoints')].replace('-', '_')
        try:
            waypoint = cls(text_list[0].replace('^col^', ':'), text_list[2], text_list[3], text_list[4], text_list[8])
            total_read += len(text)
        except ValueError:
            return ParseResult(None, total_read), '路径点坐标格式应为整数'
        except KeyError:
            return ParseResult(None, total_read), '维度格式不正确'
        return ParseResult(waypoint, total_read), ''


    def __str__(self):
        return '[name:{}, x:{}, y:{}, z:{}, dim:{}, world:{}]'.format(self.name, self.x, self.y, self.z, self.get_dim_str(self.dim_id), waypoint_config['world'])

    def get_rtext_list(self):
        voxel_command = '/newWaypoint [name:{}, x:{}, y:{}, z:{}, dim:{}, world:{}]'.format(self.name, self.x, self.y, self.z, self.get_dim_str(self.dim_id), waypoint_config['world'])
        xaero_command = 'xaero_waypoint_add:{}:{}:{}:{}:{}:6:false:0:Internal_{}_waypoints'.format(self.name.replace(':', '^col^'), self.name[0], self.x, self.y, self.z, self.get_dim_str(self.dim_id).replace('minecraft:', ''))

        waypoint_str = '{} §a({}, {}, {})§r §7@§r '.format(self.name, self.x, self.y, self.z)
        return RTextList(
				RText('[+V]', color=RColor.gold).h('§6Voxemapl§r: 左键高亮路径点, ctrl + 左键点击添加路径点').c(RAction.run_command, voxel_command),
				RText('[+X] ', color=RColor.gold).h('§6Xaeros Minimap§r: 点击添加路径点').c(RAction.run_command, xaero_command),
                waypoint_str,
                self.get_dim_rtext(self.dim_id)
		    )

# 配置
waypoint_config = {}

# 玩家当前状态
wait_voxel_waypoint = {}

class WaitStatus(Enum):
    NONE = 0
    WAIT_VOXEL_WAYPOINTS = 1
    WAIT_XAERO_WAYPOINTS = 2
    SKIP_TO_WAIT_VOXEL_WAYPOINTS = 3
    SKIP_TO_WAIT_XAERO_WAYPOINTS = 4
    WAIT_DELETE_CONFIRM = 5
    SKIP_TO_WAIT_DELETE_CONFIRM = 6

# 将要删除的 content
waypoint_delete_content = {}

def load_waypoint_config(path: str):
    global waypoint_config
    if not os.path.exists(path):
        waypoint_config['world'] = ''
        waypoint_config['permission_level'] = 2
        waypoint_config['waypoints'] = {}
        save_waypoint_config(path)

    with open(path, 'r') as waypoint_config_file:
        waypoint_config = yml.load(waypoint_config_file)


def save_waypoint_config(path: str):
    with open(path, 'w') as waypoint_config_file:
        yml.dump(waypoint_config, waypoint_config_file)


class IllegalPoint(CommandSyntaxError):
    def __init__(self, msg, char_read: int):
        super().__init__(msg, char_read)


class PointArgument(ArgumentNode):
    def parse(self, text: str) -> ParseResult:
        result, msg = Waypoint.parse(text)
        if result.value == None:
            raise IllegalPoint(msg, result.char_read)
        return result


def list_points(src: CommandSource, dim: Any):
    reply_text = ''
    dim_id = None
    try:
        dim_id = int(dim)
    except ValueError:
        pass

    if dim_id == None:
        try:
            dim_id = Waypoint.get_dim_id(dim)
        except KeyError:
            if dim != 'all':
                src.reply('§b[Waypoints]§r 找不到指定的维度')
                return
    if dim_id == None:
        # dim == all
        dim_id_list = Waypoint.get_dim_id_list()
    else:
        dim_id_list = [dim_id]

    reply_text_list = RTextList()
    for i in dim_id_list:
        count = 0
        dim_text_list = RTextList()
        for _, point in waypoint_config['waypoints'].items():
            if point.dim_id != i:
                continue
            dim_text_list.append(point.get_rtext_list(), '\n')
            count += 1
        reply_text_list.append('维度 §2{}§r 共有 §4{}§r 个路径点:\n'.format(Waypoint.get_dim_str(i), count), dim_text_list)
    reply_text_list = RTextList('§b[Waypoints]§r wp list {} 结果如下:\n'.format(dim), reply_text_list)
    src.reply(reply_text_list)


def add_voxel(src: CommandSource):
    if not check_permission(src.get_server(), src.get_info()):
        src.reply('§b[Waypoints]§r 你没有权限添加路径点！')
        return
    if src.is_player:
        src.reply('§b[Waypoints]§r 接下来请使用 voxel 将 waypoint 分享给所有人')
        wait_voxel_waypoint[src.get_info().player] = WaitStatus.SKIP_TO_WAIT_VOXEL_WAYPOINTS
    else:
        src.reply('§b[Waypoints]§r 控制台无法使用此操作')

def add_xaero(src: CommandSource):
    if not check_permission(src.get_server(), src.get_info()):
        src.reply('§b[Waypoints]§r 你没有权限添加路径点！')
        return
    if src.is_player:
        src.reply('§b[Waypoints]§r 接下来请使用 xaero 将 waypoint 分享给所有人')
        wait_voxel_waypoint[src.get_info().player] = WaitStatus.SKIP_TO_WAIT_XAERO_WAYPOINTS
    else:
        src.reply('§b[Waypoints]§r 控制台无法使用此操作')


def add_point(src: CommandSource, point: Waypoint):
    if not check_permission(src.get_server(), src.get_info()):
        src.reply('§b[Waypoints]§r 你没有权限添加路径点！')
        return
    add_point_to_db(src.get_server(), point)


def delete_point(src: CommandSource, content: str):
    if not check_permission(src.get_server(), src.get_info()):
        src.reply('§b[Waypoints]§r 你没有权限删除路径点！')
        return
    reply_text = '§b[Waypoints]§r 将要删除 §b{}§r 个名字包含 §b{}§r 的路径点:\n'
    count = 0

    for _, point in waypoint_config['waypoints'].items():
        if content not in point.name:
            continue
        reply_text += str(point) + '\n'
        count += 1
    
    reply_text += '输入 YES 确认删除，其它字符取消删除'
    src.reply(reply_text.format(count, content))
    wait_voxel_waypoint[src.get_info().player] = WaitStatus.SKIP_TO_WAIT_DELETE_CONFIRM
    waypoint_delete_content[src.get_info().player] = content

def search_point(src: CommandSource, content: str):
    reply_rtext_list = RTextList()
    count = 0
    for _, point in waypoint_config['waypoints'].items():
        if content not in point.name:
            continue
        reply_rtext_list.append(point.get_rtext_list(), '\n')
        count += 1
    reply_rtext_list = RTextList('§b[Waypoints]§r 共有 §b{}§r 个名字包含 §b{}§r 的路径点:\n'.format(count, content), reply_rtext_list)
    src.reply(reply_rtext_list)

def add_point_to_db(server: ServerInterface, point: Waypoint):
    waypoint_config['waypoints'][point.name] = point
    save_waypoint_config(waypoint_config_path)
    server.broadcast('已添加路径点 §b{}§r'.format(point))

def delete_db_point(server: ServerInterface, info: Info):
    content = waypoint_delete_content[info.player]
    reply_text = '§b[Waypoints]§r 已删除 {} 个路径点'
    count = 0

    # 使用 waypoint_config['waypoints'].items() 遍历好像没法删除
    for key in list(waypoint_config['waypoints'].keys()):
        point = waypoint_config['waypoints'][key]
        if content not in point.name:
            continue
        count += 1
        del waypoint_config['waypoints'][key]
    save_waypoint_config(waypoint_config_path)
    server.reply(info, reply_text.format(count))

def set_world(src: CommandSource, world_name: str):
    if not check_permission(src.get_server(), src.get_info()):
        src.reply('§b[Waypoints]§r 你没有权限设置 world！')
        return
    reply_text = '§b[Waypoints]§r 当前 word 已设置为 §2{}§r'
    waypoint_config['world'] = world_name
    save_waypoint_config(waypoint_config_path)
    src.get_server().broadcast(reply_text.format(world_name))

def set_permission_level(src: CommandSource, permission_level: int):
        if not check_permission(src.get_server(), src.get_info()):
            src.reply('§b[Waypoints]§r 你没有权限设置特权等级！')
            return
        reply_text = '§b[Waypoints]§r 当前 permission_level 已设置为 §2{}§r'
        waypoint_config['permission_level'] = permission_level
        save_waypoint_config(waypoint_config_path)
        src.get_server().broadcast(reply_text.format(permission_level))

def check_permission(server: ServerInterface, info: Info) -> bool:
    return server.get_permission_level(info) > waypoint_config['permission_level']

def on_load(server: ServerInterface, prev_module):
    load_waypoint_config(waypoint_config_path)
    server.register_help_message('!!wp', '获取 Waypoint 插件使用方法')
    server.register_command(
        Literal('!!wp').then(
            Literal('add').then(
                PointArgument('waypoint').runs(
                    lambda src, ctx: add_point(src, ctx['waypoint']))
            )
        ).then(
            Literal('addvoxel').runs(lambda src, ctx: add_voxel(src))
        ).then(
            Literal('addxaero').runs(lambda src, ctx: add_xaero(src))
        ).then(
            Literal('list').then(
                Text('dim').runs(
                    lambda src, ctx: list_points(src, ctx['dim']))
            ).runs(lambda src, ctx: list_points(src, 'all'))
        ).then(
            Literal('del').then(
                Text('content').runs(lambda src, ctx: delete_point(src, ctx['content']))
            )
        ).then(
            Literal('search').then(
                Text('content').runs(lambda src, ctx: search_point(src, ctx['content']))
            )
        ).then(
            Literal('set_world').then(
                Text('world_name').runs(lambda src, ctx: set_world(src, ctx['world_name']))
            )
        ).then(
            Literal('set_permission_level').then(
                Integer('set_permission_level').runs(lambda src, ctx: set_permission_level(src, ctx['set_permission_level']))
            )
        ).runs(lambda src, ctx: src.reply(help_msg))
    )


def on_player_left(server: ServerInterface, player: str):
    wait_voxel_waypoint.pop(player, None)


def on_info(server: ServerInterface, info: Info):
    wait_value = wait_voxel_waypoint.get(info.player, WaitStatus.NONE)
    if wait_value == WaitStatus.WAIT_VOXEL_WAYPOINTS:
        result, msg = Waypoint.parse(info.content)
        if result.value == None:
            server.reply(info, '§b[Waypoints]§r 路径点格式不正确，已结束添加路径点\n msg: {}'.format(msg))
            del wait_voxel_waypoint[info.player]
        else:
            add_point_to_db(server, result.value)
            server.reply(info, '§b[Waypoints]§r 请输入任意字符结束添加或者继续分享要添加的路径点')
    elif wait_value == WaitStatus.WAIT_XAERO_WAYPOINTS:
        result, msg = Waypoint.parse_xaero(info.content)
        if result.value == None:
            server.reply(info, '§b[Waypoints]§r 路径点格式不正确，已结束添加路径点\n msg: {}'.format(msg))
            del wait_voxel_waypoint[info.player]
        else:
            add_point_to_db(server, result.value)
            server.reply(info, '§b[Waypoints]§r 请输入任意字符结束添加或者继续分享要添加的路径点')
    elif wait_value == WaitStatus.SKIP_TO_WAIT_VOXEL_WAYPOINTS:
        wait_voxel_waypoint[info.player] = WaitStatus.WAIT_VOXEL_WAYPOINTS
    elif wait_value == WaitStatus.SKIP_TO_WAIT_XAERO_WAYPOINTS:
        wait_voxel_waypoint[info.player] = WaitStatus.WAIT_XAERO_WAYPOINTS
    elif wait_value == WaitStatus.WAIT_DELETE_CONFIRM:
        if info.content == 'YES':
            delete_db_point(server, info)
        else:
            server.reply(info, '§b[Waypoints]§r 取消删除路径点')
        del wait_voxel_waypoint[info.player]
    elif wait_value == WaitStatus.SKIP_TO_WAIT_DELETE_CONFIRM:
        wait_voxel_waypoint[info.player] = WaitStatus.WAIT_DELETE_CONFIRM
