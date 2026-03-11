auto_update_map: dict[str | None, str] = {
    "0": "自動更新なし / No Auto-Update",
    "1": "自動更新あり / Has Auto-Update",
    None: "未設定 / Not Set",
    "": "未設定 / Not Set",
}

contract_status_map: dict[int, str] = {
    0: "無効 / Disabled",
    1: "有効 / Enabled",
    10: "未採用 / Unused",
    11: "採用済 / Used",
    20: "仕掛中 / In Process",
    21: "署名済 / Signed",
    22: "ワークフロー完了 / Finished",
    23: "紙で署名済 / Signed by Paper",
    30: "解約 / Canceled",
    31: "契約満了 / Expired",
}

antisocial_map: dict[str | None, str] = {
    "0": "反社条項なし / No Clause",
    "1": "反社条項あり / Has Clause",
    None: "未設定 / Not Set",
    "": "未設定 / Not Set",
}


def get_auto_update_map(auto_update: str | None) -> str:
    return auto_update_map.get(auto_update, "未設定 / Not Set")


def get_contract_status_map(status: int | None) -> str:
    return contract_status_map.get(status, "未設定 / Not Set")


def get_antisocial_map(antisocial: str | None) -> str:
    return antisocial_map.get(antisocial, "未設定 / Not Set")
