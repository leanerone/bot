---
name: alarm-watch
version: 1.0.0
runtime: mcp
server: fabbot
tools:
  - alarms_open
  - watcher_summary
permissions:
  - alarms.read
  - notify.desktop
config_schema:
  - levels: 告警级别过滤 (默认 CRITICAL,ALARM)
  - hours: 回看窗口 (默认 168)
description: 查询当前未处理告警与值守概览，支持桌面通知推送（配合 Fab Bot 桌面壳）。
---

# 告警值守 Skill

查询未处理告警（分级汇总/按机台分布/明细），并可触发桌面通知。

## 工具

### alarms_open(hours: number = 168) → {alarms, summary, by_eqp}

### watcher_summary() → {alarms: {...}, wip: number}
