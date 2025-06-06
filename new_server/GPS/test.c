#include <TinyGPS++.h>
#include <SoftwareSerial.h>
#include <WiFi.h>
#include <LiquidCrystal.h> // 納入LCD顯示模組的輔助函式庫

/*
   This sample sketch demonstrates the normal use of a TinyGPS++ (TinyGPSPlus) object.
   It requires the use of SoftwareSerial, and assumes that you have a
   4800-baud serial GPS device hooked up on pins 4(rx) and 3(tx).
*/

const char* ssid = "af";          // 替換為您的 WiFi 名稱
const char* password = "icanlabst333";      // 替換為您的 WiFi 密碼

const char* serverAddress = "172.24.16.12"; // 伺服器地址（不含 http://）
int port = 5001; // HTTP 為 80，HTTPS 為 443

LiquidCrystal lcd(12, 11, 4, 5, 6, 7); // 定義LCD物件對應Arduino的腳位
static const int TXPin = 2, RXPin = 3;
static const uint32_t GPSBaud = 9600;

// The TinyGPS++ object
TinyGPSPlus gps;

// The serial connection to the GPS device
SoftwareSerial ss(RXPin, TXPin);

String lat = "120.6001", lon = "24.1790", s = "";
int delay_time = 1000;

void setup()
{
  Serial.begin(115200);
  lcd.begin(16, 2); // 初始化LCD物件的格式為16字 × 2行

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Attempting to connect to WiFi network: ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    delay(2000);
  }
  Serial.println("Wifi connected.");
  display("Wifi connected.", "");
  delay(delay_time);

  ss.begin(GPSBaud);

  Serial.println(F("DeviceExample.ino"));
  Serial.println(F("A simple demonstration of TinyGPS++ with an attached GPS module"));
  Serial.print(F("Testing TinyGPS++ library v. ")); Serial.println(TinyGPSPlus::libraryVersion());
  Serial.println(F("by Mikal Hart"));
  Serial.println();
}

void loop()
{

  // 讀取 GPS 資料流
  while (ss.available()) {
    char c = ss.read();
    gps.encode(c);
    Serial.write(c);  // 顯示原始 GPS 資料（例如 $GPGGA...）
  }

  // This sketch displays information every time a new sentence is correctly encoded.
  while (ss.available() > 0) {
    if (gps.encode(ss.read())) {
      process_Info();
      display("Lat: "+lat, "Lon: "+lon);
      delay(delay_time);  // 單位為毫秒（milliseconds），1000 ms = 1 秒
    }
  }


//   if (millis() > 5000 && gps.charsProcessed() < 10)
//   {
//     Serial.println(F("No GPS detected: check wiring."));
//     while(true);
//   }
}

void process_Info()
{
  Serial.print(F("Location: ")); 
  // if (gps.location.isValid())
  if (gps.location.isValid() && gps.location.isUpdated())
  {
    lat = String(gps.location.lat(), 6);
    lon = String(gps.location.lng(), 6);
  }
  else
  {
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Waiting GPS...");
      lcd.setCursor(0, 1);
      lcd.print("Signal:");
      lcd.print(gps.satellites.value());  // 顯示衛星數量
  }
  s = lat + "," + lon;
  Serial.println(s);
  send();
}

void send() {
    WiFiClient client;
    if (client.connect(serverAddress, port)) {
        Serial.print("Connected to server, sending: ");
        Serial.println(s);
        client.print(s);
        client.stop();
        Serial.println("→ Sent and disconnected");
    }
    else {
        Serial.println("Cannot connect to server.");
    }
}

void display(String line1, String line2) {
  lcd.clear(); // 清除LCD螢幕
  lcd.setCursor(0, 0); // 游標設到LCD第1字 × 第1行
  lcd.print(line1); // LCD顯示出字串"Hello World!"
  lcd.setCursor(0, 1); // 游標設到LCD第1字 × 第2行
  lcd.print(line2); // LCD顯示出字串"I am LCD "
}