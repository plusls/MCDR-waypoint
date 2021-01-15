# coding=utf-8
from mcdreforged.api.types import *
from mcdreforged.api.command import *
import re
import os
from typing import Any
from ruamel import yaml
from enum import Enum

yml = yaml.YAML()


waypoint_db_path = './plugins/waypoint/waypoints.yaml'   # 路径点保存位置

permission_check = False   # 权限校验开关True/False

help_msg = '''
======== §bWaypoints §r========
§b!!wp§r 显示本帮助信息
§b!!wp list§r 显示路径点列表
§b!!wp list <dim>§r 显示路径点列表（dim 可使用 1, 0, -1 代表末地，主世界，下界，或者直接使用 minecraft:the_end, minecraft:overworld, minecraft:the_nether）
§b!!wp search <content>§r 搜索含有指定内容名字的路径点
§b!!wp add [name:name, x:1, y:2, z:3, dim:minecraft:overworld] §r 添加路径点（需要 MCDR.helper 以上权限）
§b!!wp del <content>§r 删除名字包含 <content> 的路径点，会有确认信息（需要 MCDR.helper 以上权限）
'''


PLUGIN_METADATA = {
    'id': 'waypoint',
    'version': '1.0.0',
    'name': 'waypoint',
    'description': 'waypoint',  # RText component is allowed
    'author': 'plusls',
    'link': 'https://github.com/Fallen-Breath/MCDReforged',
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

    def __init__(self, name: str, x: float, y: float, z: float, dim_str: str):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.dim_id = Waypoint.get_dim_id(dim_str)

    def get_dim_id_list() -> list:
        return Waypoint.dim_id_str_map.keys()

    def get_dim_id(dim_str: str) -> int:
        return Waypoint.dim_str_id_map[dim_str]

    def get_dim_str(dim_id: int) -> str:
        return Waypoint.dim_id_str_map[dim_id]

    def parse(text: str):
        total_read = 0
        match_object = re.match(
            r"\[name:(.+?)\, x:(-?\d+), y:(-?\d+), z:(-?\d+), dim:(.+?)]", text)
        if match_object == None:
            return ParseResult(None, 0), '路径点格式不正确'

        parse_result = match_object.groups()
        total_read = match_object.span()[1]

        if len(parse_result) != 5:
            return ParseResult(None, total_read), '路径点格式不正确'

        try:
            waypoint = Waypoint(*parse_result)
        except KeyError:
            return ParseResult(None, total_read), '维度格式不正确'
        return ParseResult(waypoint, total_read), ''

    def __str__(self):
        return '[name:{}, x:{}, y:{}, z:{}, dim:{}]'.format(self.name, self.x, self.y, self.z, Waypoint.get_dim_str(self.dim_id))


# 数据库
waypoint_db = {}

# 玩家当前状态
wait_voxel_waypoint = {}

class WaitStatus(Enum):
    NONE = 0
    WAIT_WAYPOINTS = 1
    SKIP_TO_WAIT_WAYPOINTS = 2
    WAIT_DELETE_CONFIRM = 3
    SKIP_TO_WAIT_DELETE_CONFIRM = 4

# 将要删除的 content
waypoint_delete_content = {}

def load_waypoint_db(path: str):
    global waypoint_db
    if not os.path.exists(path):
        with open(path, 'w') as waypoint_db_file:
            yml.dump(waypoint_db, waypoint_db_file)

    with open(path, 'r') as waypoint_db_file:
        waypoint_db = yml.load(waypoint_db_file)
        if waypoint_db == None:
            waypoint_db = {}


def save_waypoint_db(path: str):
    with open(path, 'w') as waypoint_db_file:
        yml.dump(waypoint_db, waypoint_db_file)


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

    reply_text = ''
    for i in dim_id_list:
        count = 0
        reply_text += '维度 §b{}§r 共有 §b{}§r 个路径点:\n'
        for _, point in waypoint_db.items():
            if point.dim_id != i:
                continue
            reply_text += str(point) + '\n'
            count += 1
        reply_text = reply_text.format(Waypoint.get_dim_str(i), count)
    src.reply('§b[Waypoints]§r wp list {} 结果如下:\n{}'.format(dim, reply_text))


def add_voxel(src: CommandSource):
    if permission_check and src.get_server().get_permission_level(CommandSource.get_info()) <= 2:
        src.reply('§b[Waypoints]§r 你没有权限添加路径点！')
        return
    if src.is_player:
        src.reply('§b[Waypoints]§r 接下来请使用 voxel 将 waypoint 分享给所有人')
        wait_voxel_waypoint[src.get_info().player] = WaitStatus.SKIP_TO_WAIT_WAYPOINTS
    else:
        src.reply('§b[Waypoints]§r 控制台无法使用此操作')


def add_point(src: CommandSource, point: Waypoint):
    if permission_check and src.get_server().get_permission_level(CommandSource.get_info()) <= 2:
        src.reply('§b[Waypoints]§r 你没有权限添加路径点！')
        return
    add_point_to_db(src.get_server(), point)


def delete_point(src: CommandSource, content: str):
    if permission_check and src.get_server().get_permission_level(CommandSource.get_info()) <= 2:
        src.reply('§b[Waypoints]§r 你没有权限删除路径点！')
        return
    reply_text = '§b[Waypoints]§r 将要删除 §b{}§r 个名字包含 §b{}§r 的路径点:\n'
    count = 0

    for _, point in waypoint_db.items():
        if content not in point.name:
            continue
        reply_text += str(point) + '\n'
        count += 1
    
    reply_text += '输入 YES 确认删除，其它字符取消删除'
    src.reply(reply_text.format(count, content))
    wait_voxel_waypoint[src.get_info().player] = WaitStatus.SKIP_TO_WAIT_DELETE_CONFIRM
    waypoint_delete_content[src.get_info().player] = content

def search_point(src: CommandSource, content: str):
    reply_text = '§b[Waypoints]§r 共有 §b{}§r 个名字包含 §b{}§r 的路径点:\n'
    count = 0
    for _, point in waypoint_db.items():
        if content not in point.name:
            continue
        reply_text += str(point) + '\n'
        count += 1
    src.reply(reply_text.format(count, content))

def add_point_to_db(server: ServerInterface, point: Waypoint):
    waypoint_db[point.name] = point
    save_waypoint_db(waypoint_db_path)
    server.broadcast('已添加路径点 §b{}§r'.format(point))

def delete_db_point(server: ServerInterface, info: Info):
    content = waypoint_delete_content[info.player]
    reply_text = '§b[Waypoints]§r 已删除 {} 个路径点'
    count = 0

    # 使用 waypoint_db.items() 遍历好像没法删除
    for key in list(waypoint_db.keys()):
        point = waypoint_db[key]
        if content not in point.name:
            continue
        count += 1
        del waypoint_db[key]
    
    server.reply(info, reply_text.format(count))

def on_load(server: ServerInterface, prev_module):
    load_waypoint_db(waypoint_db_path)
    server.register_help_message('!!wp', '获取 Waypoint 插件使用方法')
    server.register_command(
        Literal('!!wp').then(
            Literal('add').then(
                PointArgument('waypoint').runs(
                    lambda src, ctx: add_point(src, ctx['waypoint']))
            ).runs(lambda src, ctx: add_voxel(src))
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
        ).runs(lambda src, ctx: src.reply(help_msg))
    )


def on_player_left(server: ServerInterface, player: str):
    wait_voxel_waypoint.pop(player)


def on_info(server: ServerInterface, info: Info):
    wait_value = wait_voxel_waypoint.get(info.player, WaitStatus.NONE)
    if wait_value == WaitStatus.WAIT_WAYPOINTS:
        result, msg = Waypoint.parse(info.content)
        if result.value == None:
            server.reply(info, '§b[Waypoints]§r 路径点格式不正确，已结束添加路径点')
            del wait_voxel_waypoint[info.player]
        else:
            add_point_to_db(server, result.value)
            server.reply(info, '§b[Waypoints]§r 请输入任意字符结束添加或者继续分享要添加的路径点')
    elif wait_value == WaitStatus.SKIP_TO_WAIT_WAYPOINTS:
        wait_voxel_waypoint[info.player] = WaitStatus.WAIT_WAYPOINTS
    elif wait_value == WaitStatus.WAIT_DELETE_CONFIRM:
        if info.content == 'YES':
            delete_db_point(server, info)
        else:
            server.reply(info, '§b[Waypoints]§r 取消删除路径点')
        del wait_voxel_waypoint[info.player]
    elif wait_value == WaitStatus.SKIP_TO_WAIT_DELETE_CONFIRM:
        wait_voxel_waypoint[info.player] = WaitStatus.WAIT_DELETE_CONFIRM
