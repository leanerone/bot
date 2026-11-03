"""MES/FDC 数据适配器接口。

真实工厂接入原则 (安全红线):
1. 只读: 适配器只实现查询, 不提供任何写操作;
2. 不直连生产网: 通过 IT 侧中间库 (定时同步的只读副本) 或只读 API;
3. 查询统一走权限校验与审计 (见 app/api)。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MESAdapter(ABC):
    @abstractmethod
    def get_lot(self, lot_id: str) -> Optional[Dict[str, Any]]:
        """按批次号查在制品信息。"""

    @abstractmethod
    def get_eqp_status(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """查机台状态, 可按群组过滤。"""

    @abstractmethod
    def get_alarms(self, hours: int = 24, only_open: bool = True) -> List[Dict[str, Any]]:
        """查最近告警, 默认只看未处理的。"""
