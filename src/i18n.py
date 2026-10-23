"""中英文字串。用 tr("key") 取得目前語言的文字。"""
from PySide6.QtCore import QLocale

LANGS = {"en": "English", "zh": "繁體中文"}

_lang = "en"

S = {
    # ---- 選單 ----
    "pomodoro":        {"en": "Pomodoro",              "zh": "番茄鐘"},
    "pomo_focus_left": {"en": "Pomodoro · focus {t}",   "zh": "番茄鐘 · 專注中 {t}"},
    "pomo_break_left": {"en": "Pomodoro · break {t}",   "zh": "番茄鐘 · 休息中 {t}"},
    "pomo_stop":       {"en": "Stop",                   "zh": "停止"},
    "focus_n":         {"en": "Focus {m} min",          "zh": "專注 {m} 分鐘"},
    "break_n":         {"en": "Break {m} min",          "zh": "休息 {m} 分鐘"},
    "focus_custom_n":  {"en": "Focus {m} min (custom)", "zh": "專注 {m} 分鐘（自訂）"},
    "custom_focus":    {"en": "Custom focus time...",   "zh": "自訂專注時間⋯"},
    "custom_break":    {"en": "Custom break time...",   "zh": "自訂休息時間⋯"},
    "pick_focus":      {"en": "Focus for how long?",    "zh": "要專注多久？"},
    "pick_break":      {"en": "Break for how long?",    "zh": "要休息多久？"},
    "pick_hint_break": {"en": "Used after every focus.", "zh": "之後每次專注結束都會用這個長度。"},
    "minutes":         {"en": "min",                    "zh": "分鐘"},
    "start":           {"en": "Start",                  "zh": "開始"},
    "cancel":          {"en": "Cancel",                 "zh": "取消"},
    "todo":            {"en": "To-do list",             "zh": "待辦清單"},
    "feed":            {"en": "Feed a treat",           "zh": "餵罐罐"},
    "mode":            {"en": "Mode",                   "zh": "模式"},
    "color":           {"en": "Color",                  "zh": "顏色"},
    "facing":          {"en": "Idle facing",            "zh": "待著時的方向"},
    "size":            {"en": "Size",                   "zh": "大小"},
    "add_cat":         {"en": "Add a cat",              "zh": "多一隻貓"},
    "remove_cat":      {"en": "Say goodbye to this cat", "zh": "送走這隻貓"},
    "settings":        {"en": "Settings",               "zh": "設定"},
    "remind":          {"en": "Break reminders",        "zh": "休息提醒"},
    "off":             {"en": "Off",                    "zh": "關閉"},
    "every_n":         {"en": "Every {m} min",          "zh": "每 {m} 分鐘"},
    "nap_after":       {"en": "Nap when idle for",      "zh": "閒置多久會睡覺"},
    "never":           {"en": "Never",                  "zh": "不睡覺"},
    "n_min":           {"en": "{m} min",                "zh": "{m} 分鐘"},
    "battery_alert":   {"en": "Low battery alerts",     "zh": "低電量提醒"},
    "language":        {"en": "Language",               "zh": "語言"},
    "quit":            {"en": "Quit",                   "zh": "結束"},

    "mode_idle":       {"en": "Stay put",               "zh": "待著不動"},
    "mode_random":     {"en": "Wander",                 "zh": "隨意漫步"},
    "mode_follow":     {"en": "Follow the cursor",      "zh": "跟著滑鼠"},
    "mode_windows":    {"en": "Walk on windows",        "zh": "在視窗上走"},
    "mode_sleep":      {"en": "Sleep",                  "zh": "睡覺"},
    "color_black":     {"en": "Black",                  "zh": "黑貓"},
    "color_white":     {"en": "White",                  "zh": "白貓"},
    "color_orange":    {"en": "Orange",                 "zh": "橘貓"},
    "color_brown":     {"en": "Brown",                  "zh": "棕貓"},
    "dir_down":        {"en": "Front",                  "zh": "面向前"},
    "dir_left":        {"en": "Left",                   "zh": "面向左"},
    "dir_right":       {"en": "Right",                  "zh": "面向右"},
    "dir_up":          {"en": "Back",                   "zh": "背對"},
    "size_2":          {"en": "Small",                  "zh": "小"},
    "size_3":          {"en": "Medium",                 "zh": "中"},
    "size_4":          {"en": "Large",                  "zh": "大"},

    "feed_all":        {"en": "Feed everyone",          "zh": "餵全部的貓"},
    "flavor_tuna":     {"en": "Tuna",                   "zh": "鮪魚"},
    "flavor_chicken":  {"en": "Chicken",                "zh": "雞肉"},
    "flavor_salmon":   {"en": "Salmon",                 "zh": "鮭魚"},
    "flavor_catnip":   {"en": "Catnip",                 "zh": "貓薄荷"},
    "flavor_bitter":   {"en": "Bitter melon",           "zh": "苦瓜"},
    "flavor_random":   {"en": "Surprise me",            "zh": "隨機口味"},
    "go_home":         {"en": "Go home",                "zh": "回家"},
    "go_home_all":     {"en": "Everyone go home",       "zh": "全部回家"},
    "come_out":        {"en": "Come out and play",      "zh": "出來玩"},
    "house_show":      {"en": "Show cat house",         "zh": "顯示貓屋"},
    "house_hide":      {"en": "Hide cat house",         "zh": "收起貓屋"},
    "all_mode":        {"en": "Mode for all cats",      "zh": "全部貓咪的模式"},
    "palette":         {"en": "Cat palette...",         "zh": "貓咪調色盤⋯"},
    "palette_title":   {"en": "Cat palette",            "zh": "貓咪調色盤"},
    "fur":             {"en": "Fur",                    "zh": "毛色"},
    "eyes":            {"en": "Eyes",                   "zh": "眼睛"},
    "my_colors":       {"en": "My colors",              "zh": "我的毛色"},
    "save_apply":      {"en": "Save",                   "zh": "儲存"},
    "custom_n":        {"en": "Custom {n}",             "zh": "自訂 {n}"},
    "recent":          {"en": "Recent",                 "zh": "最近"},
    "delete":          {"en": "Delete",                 "zh": "刪除"},

    # ---- 貓咪說的話 ----
    "say_focus":       {"en": "Focus for {m} minutes. You got this!", "zh": "開始專注 {m} 分鐘，加油！"},
    "say_focus_done":  {"en": "Focus done! Take a {m}-minute break.", "zh": "專注結束！休息 {m} 分鐘吧。"},
    "say_break_done":  {"en": "Break's over. Back to it!",            "zh": "休息結束，繼續加油！"},
    "say_all_done":    {"en": "All done! Amazing!",                   "zh": "全部完成！好厲害！"},
    "say_hello":       {"en": "Meow! I'm here.",                      "zh": "喵！我來了。"},
    "say_morning":     {"en": "Meow, good morning!",                  "zh": "喵～早安！"},
    "say_pet":         {"en": ["Purrr...", "Meow~", "That feels nice."],
                        "zh": ["呼嚕呼嚕～", "喵～", "好舒服～"]},
    "say_can":         {"en": "A treat?!",                            "zh": "罐罐？！"},
    "say_yummy":       {"en": "Yummy! Thank you.",                    "zh": "好吃！謝謝。"},
    "say_remind":      {"en": ["Time to stand up and stretch.",
                               "Have a sip of water.",
                               "Rest your eyes. Look far away.",
                               "Relax your shoulders and breathe.",
                               "You've been sitting a while. Take a walk."],
                        "zh": ["站起來伸個懶腰吧。",
                               "喝口水吧。",
                               "眼睛休息一下，看看遠方。",
                               "肩膀放鬆，深呼吸。",
                               "坐太久了，起來走走吧。"]},
    "react_tuna":      {"en": "Yummy tuna!",                    "zh": "鮪魚好好吃！"},
    "react_chicken":   {"en": "Chicken... purrr.",              "zh": "雞肉～呼嚕呼嚕。"},
    "react_salmon":    {"en": "SALMON!!! Best day ever!",       "zh": "是鮭魚！！最棒的一天！"},
    "react_catnip":    {"en": "Catnip! Zoomies!",               "zh": "貓薄荷！衝啊！"},
    "react_dizzy":     {"en": "Whoa... the room is spinning.",  "zh": "頭好暈……"},
    "react_bitter":    {"en": "Bleh! That's bitter!",           "zh": "噁！好苦！"},
    "say_batt_low":    {"en": "Battery at {p}%... so sleepy. Please charge me.",
                        "zh": "電量只剩 {p}%……好睏，快充電。"},
    "say_batt_thanks": {"en": "Thanks for charging me!",              "zh": "謝謝你幫我充電！"},

    # ---- 待辦清單 ----
    "todo_title":      {"en": "Today's quests",         "zh": "今天的任務"},
    "todo_add":        {"en": "New quest, then Enter",  "zh": "新增任務，按 Enter"},
    "todo_clear":      {"en": "Clear done",             "zh": "清除已完成"},
    "todo_count":      {"en": "{d} / {n} done",         "zh": "完成 {d} / {n}"},
    "todo_empty":      {"en": "No quests yet",          "zh": "還沒有任務"},
}


def system_default():
    return "zh" if QLocale.system().name().lower().startswith("zh") else "en"


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "en"


def lang():
    return _lang


def tr(key, **kw):
    v = S[key][_lang]
    if isinstance(v, list):
        return v
    return v.format(**kw) if kw else v
