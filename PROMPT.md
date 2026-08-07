# پرامپت جامع: بازی مبارزه‌ای زورخانه (Zoorkhane Fighting Game)

## توضیحات کلی پروژه

این پروژه یک بازی مبارزه‌ای دو بعدی است که با استفاده از کتابخانه Pygame پیاده‌سازی شده است. بازی قابلیت حالت‌های مختلف بازی از جمله بازیکن در مقابل بازیکن، بازیکن در مقابل هوش مصنوعی و هوش مصنوعی در مقابل هوش مصنوعی را دارد.

---

## ساختار پروژه

```
Zoorkhane/
├── GAMECODE-python.py          # فایل اصلی بازی
├── fighter.py                  # کلاس مبارز
├── agent.py                    # عامل هوش مصنوعی اصلی
├── agent_cpp.cpp               # پیاده‌سازی عامل با C++
├── random-agent.py             # عامل هوش مصنوعی پیشرفته
├── json.hpp                    # کتابخانه JSON برای C++
├── Background/                 # تصاویر پس‌زمینه
├── Good Fighter/               # تصاویر مبارزان
├── intro/                      # تصاویر معرفی
└── music/                      # فایل‌های صوتی
```

---

## جزئیات فنی بازی

### 1. مشخصات محیط بازی

- **ابعاد صفحه**: 1000 × 600 پیکسل
- **FPS**: 60 فریم در ثانیه
- **مدت زمان بازی**: 3600 فریم (60 ثانیه)
- **سلامت اولیه**: هر مبارز با 100 واحد سلامت شروع می‌کند

### 2. سیستم کنترل بازیکن

مبارزان با استفاده از کلیدهای زیر کنترل می‌شوند:

**بازیکن 1:**
- `A` و `D`: حرکت چپ/راست
- `W`: پرش
- `R`, `T`: حمله سبک
- `F`, `G`: حمله سنگین
- `S` + `A`/`D`: داش (حرکت سریع)

**بازیکن 2:**
- فلش‌های چپ و راست: حرکت
- فلش بالا: پرش
- `Keypad 1`, `Keypad 2`: حمله سبک
- `Keypad 4`, `Keypad 5`: حمله سنگین
- فلش پایین + چپ/راست: داش

---

## سیستم هوش مصنوعی (Advanced Fighter AI)

### کلاس AdvancedFighterAI

این کلاس یک عامل هوش مصنوعی پیشرفته است که با استفاده از تکنیک‌های مختلف یادگیری ماشین و استراتژی‌های بازی عمل می‌کند.

### پارامترهای اصلی:

```python
class AdvancedFighterAI:
    def __init__(self):
        # محدوده بهینه برای حمله
        self.ideal_attack_range = (130, 170)
        
        # فاصله امن از حریف
        self.safe_distance = 250
        
        # آستانه‌های تهاجمی بودن
        self.aggression_threshold = 0.7
        self.defensive_threshold = 0.3
        
        # شمارنده فریم برای ردیابی زمان
        self.frame_counter = 0
```

---

## ویژگی‌های هوش مصنوعی

### 1. مدل مارکوف برای پیش‌بینی حرکات حریف

```python
def predict_opponent_action(self, saved_data, distance):
    """
    پیش‌بینی حرکت بعدی حریف با استفاده از مدل مارکوف
    
    ورودی:
    - saved_data: داده‌های ذخیره شده از بازی‌های قبلی
    - distance: فاصله فعلی تا حریف
    
    خروجی:
    - پیش‌بینی حرکت بعدی حریف (attack/move/defend/jump)
    """
```

**مثال استفاده:**
```python
# فرض کنید حریف در 10 حرکت اخیر:
# - 6 بار حمله کرده
# - 3 بار حرکت کرده
# - 1 بار پریده
# احتمال حمله در حرکت بعدی: 60%
```

### 2. محاسبه میزان تهاجمی بودن حریف

```python
def calculate_opponent_aggression(self, saved_data):
    """
    اندازه‌گیری میزان تهاجمی بودن حریف
    
    خروجی: عددی بین 0 تا 1
    - 0: کاملاً دفاعی
    - 0.5: متعادل
    - 1: کاملاً تهاجمی
    """
```

**مثال:**
```python
# اگر حریف در 20 حرکت اخیر 15 بار حمله کرده باشد:
aggression_score = 15/20 = 0.75  # بسیار تهاجمی
```

### 3. استراتژی‌های بازی

سیستم هوش مصنوعی 5 استراتژی اصلی دارد:

#### الف) استراتژی دفاعی (Defensive)

- **شرایط فعال‌سازی**: وقتی سلامت بازیکن 30 واحد بیشتر از حریف باشد
- **رفتار**: فاصله امن حفظ می‌شود و حملات محتاطانه انجام می‌شود

```python
if health_diff > 30:
    strategy = "defensive"
    # فاصله امن: 250 پیکسل
    # حملات کمتر و دقیق‌تر
```

#### ب) استراتژی تهاجمی (Aggressive)

- **شرایط فعال‌سازی**: وقتی سلامت بازیکن 20 واحد کمتر از حریف باشد
- **رفتار**: حملات مکرر و نزدیک شدن به حریف

```python
if health_diff < -20:
    strategy = "aggressive"
    # تلاش برای نزدیک شدن
    # حملات مکرر و سریع
```

#### ج) استراتژی متقابل (Counter)

- **شرایط فعال‌سازی**: وقتی حریف بسیار تهاجمی است (aggression > 0.7)
- **رفتار**: دفاع و ضد حمله

#### د) استراتژی فشار (Press)

- **شرایط فعال‌سازی**: وقتی حریف منفعل است (aggression < 0.3)
- **رفتار**: فشار مداوم و حملات پیوسته

#### هـ) استراتژی متعادل (Balanced)

- **شرایط فعال‌سازی**: در سایر شرایط
- **رفتار**: ترکیبی از دفاع و حمله

---

## سیستم حملات

### انواع حملات:

1. **حمله سبک (Light Attack)**
   - خسارت: متوسط
   - سرعت: سریع
   - کولداون: کوتاه

2. **حمله سنگین (Heavy Attack)**
   - خسارت: زیاد
   - سرعت: کند
   - کولداون: طولانی

### سیستم کولداون:

```python
light_cd, heavy_cd = fighter_info['attack_cooldown']
dash_cd = fighter_info['dash_cooldown']

# اگر کولداون = 0 باشد، حمله قابل استفاده است
if heavy_cd == 0 and random.random() < 0.4:
    actions['attack'] = 2  # حمله سنگین
elif light_cd == 0 and random.random() < 0.6:
    actions['attack'] = 1  # حمله سبک
```

---

## ساختار داده‌های ورودی/خروجی

### ورودی به عامل هوش مصنوعی:

```json
{
    "fighter": {
        "x": 100,              // موقعیت افقی
        "y": 290,              // موقعیت عمودی
        "health": 75,          // سلامت فعلی
        "attack_cooldown": [0, 5],  // [light_cd, heavy_cd]
        "dash_cooldown": 0     // کولداون داش
    },
    "opponent": {
        "x": 500,
        "y": 290,
        "health": 60
    },
    "saved_data": {
        "opponent_model": {
            "action_history": [],
            "markov_transitions": {},
            "last_actions": []
        }
    }
}
```

### خروجی عامل هوش مصنوعی:

```json
{
    "move": "right",        // null, "left", "right"
    "attack": 2,            // null, 1 (light), 2 (heavy)
    "jump": false,          // true/false
    "dash": null,           // null, "left", "right"
    "debug": "strategy: aggressive; distance: 150",
    "saved_data": {
        // داده‌های به‌روز شده برای فریم بعدی
    }
}
```

---

## مثال‌های کاربردی

### مثال 1: تصمیم‌گیری در فاصله نزدیک

```python
# فرض: فاصله = 140 پیکسل (در محدوده حمله)
distance = 140
light_cd, heavy_cd = 0, 0  # هر دو حمله آماده

# استراتژی: تهاجمی
# تصمیم: حمله سنگین با احتمال 40٪
if random.random() < 0.4:
    action = "heavy_attack"
else:
    action = "light_attack"
```

### مثال 2: فرار از حریف تهاجمی

```python
# حریف بسیار تهاجمی است (aggression = 0.85)
# سلامت شما: 40، سلامت حریف: 70
# فاصله: 120 پیکسل

strategy = "counter"  # استراتژی متقابل
if fighter_x < opponent_x:
    move_direction = "left"  # فرار به چپ
    target_position = opponent_x - 250  # فاصله امن
else:
    move_direction = "right"
    target_position = opponent_x + 250
```

### مثال 3: استفاده از داش

```python
# فاصله از حریف: 300 پیکسل
# استراتژی: تهاجمی
# داش آماده است (dash_cd = 0)

if distance > 200 and strategy in ["aggressive", "press"]:
    if random.random() < 0.3:
        # با احتمال 30٪ از داش استفاده کن
        dash_direction = "right" if fighter_x < opponent_x else "left"
```

---

## الگوریتم تصمیم‌گیری کامل

```python
def make_move(fighter_info, opponent_info, saved_data):
    # 1. محاسبه متغیرهای بازی
    distance = abs(fighter_info['x'] - opponent_info['x'])
    health_diff = fighter_info['health'] - opponent_info['health']
    opponent_aggression = calculate_opponent_aggression(saved_data)
    
    # 2. پیش‌بینی حرکت حریف
    predicted_action = predict_opponent_action(saved_data, distance)
    
    # 3. انتخاب استراتژی
    strategy = determine_strategy(health_diff, opponent_aggression)
    
    # 4. تصمیم‌گیری بر اساس استراتژی
    if strategy == "defensive":
        # حفظ فاصله و حملات محتاطانه
        if distance < safe_distance:
            move = "away_from_opponent"
        if in_attack_range and cooldown_ready:
            attack = "light"
    
    elif strategy == "aggressive":
        # نزدیک شدن و حملات مکرر
        if distance > ideal_range:
            move = "toward_opponent"
        if in_attack_range:
            attack = "heavy" if heavy_ready else "light"
    
    # 5. بازگشت اقدامات
    return {
        'move': move,
        'attack': attack,
        'jump': should_jump,
        'dash': dash_direction,
        'saved_data': updated_data
    }
```

---

## نکات بهینه‌سازی

### 1. مدیریت کولداون

- همیشه وضعیت کولداون‌ها را بررسی کنید
- از حملات سنگین در مواقع حساس استفاده کنید

### 2. پیش‌بینی حرکات

- حداقل 10 حرکت اخیر حریف را ذخیره کنید
- از مدل مارکوف برای پیش‌بینی استفاده کنید

### 3. مدیریت فاصله

- محدوده بهینه: 130-170 پیکسل
- فاصله امن: 250+ پیکسل

### 4. تصادفی‌سازی

- از پرش‌های تصادفی برای جلوگیری از پیش‌بینی‌پذیری استفاده کنید
- هر 40 فریم یک بار پرش تصادفی

---

## چالش‌های پیاده‌سازی

### چالش 1: ارتباط پایتون/C++

بازی از JSON برای ارتباط بین کد پایتون و عوامل C++ استفاده می‌کند:

```cpp
// در agent_cpp.cpp
#include "json.hpp"
using json = nlohmann::json;

// دریافت ورودی از بازی
std::string input;
std::getline(std::cin, input);
auto data = json::parse(input);

// پردازش و ارسال خروجی
json output = {
    {"move", "right"},
    {"attack", 1}
};
std::cout << output.dump() << std::endl;
```

### چالش 2: ذخیره‌سازی حالت

داده‌های بین فریم‌ها باید حفظ شوند:

```python
saved_data = {
    'opponent_model': {
        'action_history': deque(maxlen=50),
        'markov_transitions': defaultdict(lambda: defaultdict(int)),
        'last_actions': deque(maxlen=10)
    },
    'game_state': {
        'last_health': [100, 100],
        'consecutive_hits': 0
    }
}
```

---

## آزمایش و ارزیابی

برای آزمایش عامل هوش مصنوعی خود:

1. **حالت AI vs AI**: مقایسه دو استراتژی مختلف
2. **امتیازدهی بر اساس**:
   - درصد پیروزی
   - میانگین سلامت باقی‌مانده
   - تعداد حملات موفق
   - کارایی استفاده از کولداون‌ها

---

## راهنمای اجرا

### نصب وابستگی‌ها:

```bash
pip install pygame numpy
```

### اجرای بازی:

```bash
python GAMECODE-python.py
```

### تنظیم حالت بازی:

در فایل `GAMECODE-python.py`، متغیر `game_mode` را تغییر دهید:

```python
# حالت‌های موجود:
game_mode = "ai_vs_ai"        # هوش مصنوعی در مقابل هوش مصنوعی
game_mode = "player_vs_ai"    # بازیکن در مقابل هوش مصنوعی
game_mode = "player_vs_player"  # بازیکن در مقابل بازیکن
```

### انتخاب عامل هوش مصنوعی:

```python
agent1_info = {
    'enabled': True,
    'language': 'python',  # یا 'cpp'
    'path': os.path.join(os.path.dirname(__file__), 'random-agent.py')
}

agent2_info = {
    'enabled': True,
    'language': 'python',
    'path': os.path.join(os.path.dirname(__file__), 'agent.py')
}
```

---

## توسعه عامل هوش مصنوعی سفارشی

برای ساخت عامل هوش مصنوعی خود:

1. فایل جدیدی مثل `my_agent.py` بسازید
2. تابع `make_move` را پیاده‌سازی کنید
3. ورودی JSON را دریافت و پردازش کنید
4. خروجی JSON را برگردانید

**ساختار پایه:**

```python
import json

def make_move(fighter_info, opponent_info, saved_data):
    # منطق تصمیم‌گیری شما
    
    actions = {
        'move': None,      # 'left', 'right', یا None
        'attack': None,    # 1 (light), 2 (heavy), یا None
        'jump': False,     # True یا False
        'dash': None,      # 'left', 'right', یا None
        'debug': '',       # پیام دیباگ (اختیاری)
        'saved_data': saved_data  # داده‌ها برای فریم بعدی
    }
    
    return actions

# رابط ورودی/خروجی
if __name__ == "__main__":
    input_data = input()
    json_data = json.loads(input_data)
    
    fighter_info = json_data['fighter']
    opponent_info = json_data['opponent']
    saved_data = json_data.get('saved_data', {})
    
    result = make_move(fighter_info, opponent_info, saved_data)
    print(json.dumps(result))
```

---

## نکات پیشرفته

### 1. استفاده از الگوریتم‌های یادگیری تقویتی

می‌توانید از Q-Learning یا Deep Q-Network (DQN) استفاده کنید:

```python
# مثال ساده Q-Learning
Q = {}  # جدول Q

def get_state(fighter_info, opponent_info):
    distance = abs(fighter_info['x'] - opponent_info['x'])
    health_diff = fighter_info['health'] - opponent_info['health']
    return (distance // 50, health_diff // 10)

def choose_action(state, epsilon=0.1):
    if random.random() < epsilon:
        return random.choice(actions)
    else:
        return max(actions, key=lambda a: Q.get((state, a), 0))
```

### 2. تحلیل الگوهای بازی

```python
def analyze_pattern(action_history):
    # شناسایی الگوهای تکراری
    patterns = {}
    for i in range(len(action_history) - 2):
        pattern = tuple(action_history[i:i+3])
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return patterns
```

### 3. پیش‌بینی پیشرفته

```python
def advanced_prediction(saved_data, distance, health_diff):
    # ترکیب چند فاکتور برای پیش‌بینی
    factors = {
        'distance': distance,
        'health': health_diff,
        'aggression': calculate_aggression(saved_data),
        'pattern': detect_pattern(saved_data)
    }
    
    # استفاده از وزن‌دهی
    prediction_score = (
        factors['distance'] * 0.3 +
        factors['health'] * 0.2 +
        factors['aggression'] * 0.3 +
        factors['pattern'] * 0.2
    )
    
    return prediction_score
```

---

این پرامپت جامع تمام جزئیات لازم برای درک، پیاده‌سازی و بهینه‌سازی یک عامل هوش مصنوعی برای بازی زورخانه را فراهم می‌کند. می‌توانید از این اطلاعات برای ساخت استراتژی‌های پیچیده‌تر و هوشمندتر استفاده کنید.
