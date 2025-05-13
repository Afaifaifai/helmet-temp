#include <LiquidCrystal.h> // 納入LCD顯示模組的輔助函式庫

LiquidCrystal lcd(2, 3, 4, 5, 6, 7); // 定義LCD物件對應Arduino的腳位
// LiquidCrystal(rs, enable, d4, d5, d6, d7)
void setup() { // 只會執行一次的程式初始化函式
  lcd.begin(16, 2); // 初始化LCD物件的格式為16字 × 2行
  Serial.begin(115200); // 設定RS232埠傳輸率9600觀看輸入類比數值
  Serial.println("Begin");
} // 結束setup()函式

void loop() { // 永遠重複執行的主控迴圈函式
  lcd.clear(); // 清除LCD螢幕
  lcd.setCursor(0, 0); // 游標設到LCD第1字 × 第1行
  lcd.print("Hello World"); // LCD顯示出字串"Hello World!"
  lcd.setCursor(0, 1); // 游標設到LCD第1字 × 第2行
  lcd.print("Hello World2"); // LCD顯示出字串"I am LCD "

  delay(1000);
}