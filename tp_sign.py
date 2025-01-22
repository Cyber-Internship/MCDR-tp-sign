# encoding=utf-8
from mcdreforged.api.command import Literal, GreedyText, ArgumentNode, CommandSyntaxError, ParseResult, command_builder_utils
from mcdreforged.api.types import PluginServerInterface, CommandSource
from mcdreforged.api.decorator import new_thread

import json
import hjson


PLUGIN_METADATA = {
    "id": "tp_sign",
    "version": "0.0.1",
    "name": "MCDR-tp-sign",
    "description": "将玩家看向的告示牌转换为可点击的传送牌",
    "author": "geniucker-dev",
    "link": "https://github.com/",
    "dependencies": {
        "mcdreforged": ">=2.0.0",
        "minecraft_data_api": "*",
    }
}

class IllegalPoint(CommandSyntaxError):
    def __init__(self, char_read: int):
        super().__init__("Invalid Point", char_read)

class DimintionError(CommandSyntaxError):
    def __init__(self, char_read: int):
        super().__init__("Invalid Dimension, only support 'overworld', 'the_nether', 'the_end'", char_read)

class IncompleteError(CommandSyntaxError):
    def __init__(self, char_read: int):
        super().__init__("Incomplete", char_read)

class PointArgument(ArgumentNode):
    def parse(self, text: str) -> ParseResult:
        total_read = 0
        coords = []
        for i in range(3):
            total_read += len(text[total_read:]) - len(command_builder_utils.remove_divider_prefix(text[total_read:]))
            value, read = command_builder_utils.get_int(text[total_read:])
            if read == 0:
                raise IllegalPoint(total_read)
            total_read += read
            if value is None:
                raise IllegalPoint(total_read)
            coords.append(value)
        return ParseResult(coords, total_read)

class DimensionArgument(ArgumentNode):
    def parse(self, text: str) -> ParseResult:
        value = command_builder_utils.get_element(text)
        read = len(value)
        if read == 0:
            raise IncompleteError(read)
        if value not in ("overworld", "the_nether", "the_end"):
            raise DimintionError(read)
        return ParseResult(value, read)


@new_thread(PLUGIN_METADATA["id"])
def tp_sign_callback(src: CommandSource, ctx: dict):
    import minecraft_data_api as api
    from  minecraft_data_api.json_parser import MinecraftJsonParser
    import math
    server = src.get_server()

    MAX_DISTANCE = 5

    player_x, player_y, z = api.get_player_info(src.player, "Pos")
    player_y += 1.62
    dimension = api.get_player_info(src.player, "Dimension")
    yaw, pitch = api.get_player_info(src.player, "Rotation")
    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)

    dx = -math.sin(yaw_rad) * math.cos(pitch_rad)
    dy = -math.sin(pitch_rad)
    dz = math.cos(yaw_rad) * math.cos(pitch_rad)

    # traverse blocks in the direction of sight within a certain distance
    for i in range(MAX_DISTANCE):
        tx = math.floor(player_x + dx * i)
        ty = math.floor(player_y + dy * i)
        tz = math.floor(z + dz * i)
        block_data = server.rcon_query(f"execute in {dimension} run data get block {tx} {ty} {tz}")
        # skip if it's not a block
        if " has the following block data: " not in block_data:
            continue
        block_data_json = hjson.loads(MinecraftJsonParser.preprocess_minecraft_json(block_data.split(" has the following block data: ")[1]))
        # if the block is a sign
        if block_data_json["id"] == "minecraft:sign":
            px, py, pz, dim, remark = *ctx["coords"], ctx["dim"], ctx["remark"]
            clickEvent = {
                "action": "run_command",
                "value": f"/execute in {dim} run tp {src.player} {px} {py} {pz}"
            }
            MESSAGES = [
                {
                    "text": "[点击传送]",
                    "clickEvent": clickEvent
                },
                {
                    "text": "",
                    "clickEvent": clickEvent
                },
                {
                    "text": f"{px} {py} {pz}",
                    "clickEvent": clickEvent
                },
                {
                    "text": remark,
                    "clickEvent": clickEvent
                }
            ]
            MESSAGES = "[{}]".format(
                ",".join([f"'{json.dumps(i, ensure_ascii=False)}'" for i in MESSAGES])
            )
            server.execute(f"execute in {dimension} run data merge block {tx} {ty} {tz} {{front_text:{{messages:{MESSAGES},has_glowing_text:1}},back_text:{{messages:{MESSAGES},has_glowing_text:1}}}}")
            return
        else:
            continue

    src.reply("请瞄准告示牌再试一次")


def on_load(server: PluginServerInterface, prev):
    server.register_command(
        Literal("!!tp_sign").then(
            PointArgument("coords").then(
                DimensionArgument("dim").then(
                    GreedyText("remark").runs(tp_sign_callback)
                )
            )
        )
    )
    server.register_help_message("!!tp_sign <x> <y> <z> <dimension> <remark>", "将玩家看向的告示牌转换为可点击的传送牌")
