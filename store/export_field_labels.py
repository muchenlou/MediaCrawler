# -*- coding: utf-8 -*-
"""Human-readable field labels and value normalization for file exports."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

XHS_CONTENT_FIELD_LABELS = {
    "source_keyword": "来源关键词",
    "note_id": "笔记ID",
    "note_url": "笔记链接",
    "type": "笔记类型",
    "title": "笔记标题",
    "desc": "正文描述",
    "time": "发布时间",
    "last_update_time": "最后更新时间",
    "user_id": "作者ID",
    "nickname": "作者昵称",
    "avatar": "作者头像",
    "ip_location": "IP属地",
    "liked_count": "点赞数",
    "collected_count": "收藏数",
    "comment_count": "评论数",
    "share_count": "分享数",
    "video_url": "视频链接",
    "xsec_token": "安全校验令牌",
    "last_modify_ts": "采集更新时间",
    "image_list": "图片链接",
    "tag_list": "话题标签",
}

XHS_COMMENT_FIELD_LABELS = {
    "note_id": "所属笔记ID",
    "comment_id": "评论ID",
    "parent_comment_id": "父评论ID",
    "content": "评论内容",
    "create_time": "评论时间",
    "user_id": "评论用户ID",
    "nickname": "评论用户昵称",
    "avatar": "评论用户头像",
    "ip_location": "IP属地",
    "like_count": "评论点赞数",
    "sub_comment_count": "子评论数",
    "pictures": "评论图片",
    "last_modify_ts": "采集更新时间",
}

XHS_CREATOR_FIELD_LABELS = {
    "user_id": "创作者ID",
    "nickname": "创作者昵称",
    "gender": "性别",
    "avatar": "头像",
    "desc": "个人简介",
    "ip_location": "IP属地",
    "follows": "关注数",
    "fans": "粉丝数",
    "interaction": "互动量",
    "tag_list": "标签",
    "last_modify_ts": "采集更新时间",
}

XHS_FIELD_LABELS_BY_ITEM_TYPE = {
    "content": XHS_CONTENT_FIELD_LABELS,
    "contents": XHS_CONTENT_FIELD_LABELS,
    "comment": XHS_COMMENT_FIELD_LABELS,
    "comments": XHS_COMMENT_FIELD_LABELS,
    "creator": XHS_CREATOR_FIELD_LABELS,
    "creators": XHS_CREATOR_FIELD_LABELS,
}

XHS_TIME_FIELDS = {
    "time",
    "last_update_time",
    "create_time",
    "last_modify_ts",
}

CHINA_TIMEZONE = timezone(timedelta(hours=8))


def _format_china_time(value: Any) -> Any:
    if value in ("", None):
        return value

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return value

    if timestamp <= 0:
        return ""

    if timestamp > 1000000000000:
        timestamp = timestamp / 1000

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(CHINA_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def prepare_export_item(platform: str, item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
    if platform != "xhs":
        return dict(item)

    prepared = dict(item)
    if item_type in {"content", "contents"}:
        # Business users prefer the note title over opaque note ids in content exports.
        prepared.pop("note_id", None)

    for field_name in XHS_TIME_FIELDS:
        if field_name in prepared:
            prepared[field_name] = _format_china_time(prepared[field_name])

    return prepared


def get_export_field_label(platform: str, field_name: str, item_type: str) -> str:
    if platform != "xhs":
        return field_name

    labels = XHS_FIELD_LABELS_BY_ITEM_TYPE.get(item_type, {})
    if field_name in labels:
        return labels[field_name]
    if field_name.startswith("tag_"):
        return f"话题标签{field_name.removeprefix('tag_')}"
    if field_name.startswith("image_"):
        return f"图片链接{field_name.removeprefix('image_')}"
    if field_name.startswith("picture_"):
        return f"评论图片{field_name.removeprefix('picture_')}"
    return field_name


def translate_export_item_keys(platform: str, item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
    item = prepare_export_item(platform, item, item_type)
    return {
        get_export_field_label(platform, key, item_type): value
        for key, value in item.items()
    }
