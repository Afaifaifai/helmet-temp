#include <WiFi.h>
#include <ArduinoHttpClient.h>

int sensorValue = 0; // 類比數值
int led_Value = 0; // 控制LED亮度的數值
float voltage = 0; // 轉換為電壓值

const char* ssid = "af";          // 替換為您的 WiFi 名稱
const char* password = "icanlabst333";      // 替換為您的 WiFi 密碼

const char* serverUrl = "http://192.168.19.72:8080/sensor"; // 替換為您的目標 URL
const char* serverAddress = "172.24.16.12"; // 伺服器地址（不含 http://）
int port = 8080; // HTTP 為 80，HTTPS 為 443
// 建立 WiFi 客戶端和 HTTP 客戶端
WiFiClient wifi;
HttpClient client = HttpClient(wifi, serverAddress, port);

void setup() {
  Serial.begin(115200);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Attempting to connect to WiFi network: ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    delay(5000);
  }
}

void loop() {
  
}

// void loop() {
//   sensorValue = analogRead(A0); // 讀取輸入A0類比數值
//   Serial.println(".........");
//   Serial.println(sensorValue);
    
//   voltage = sensorValue * (5.0 / 1023.0); // 將類比數值 (0-1023) 轉換為電壓值 (0-5V)
//   if (voltage > 2.5) { // 如果電壓超過2.5V
//       sensorValue = 512;
//       voltage = 2.5; // 將電壓值固定在最大2.5V
//   }
//   led_Value = 255 - (128 - sensorValue / 4) * 10;
//   Serial.println(voltage);


//     // 構建 JSON 數據
//     String jsonData = "{\"voltage\":" + String(voltage, 2) + ",\"led_value\":" + String(led_Value) + "}";

//     // 構建 HTTP POST 請求
//     client.beginRequest();
//     client.put("/sensor"); // 根據您的 API 路徑進行修改
//     client.sendHeader("Content-Type", "application/json");
//     client.sendHeader("Content-Length", jsonData.length());
//     client.beginBody();
//     client.print(jsonData);
//     client.endRequest();
    
//     // 讀取伺服器回應
//     int statusCode = client.responseStatusCode();
//     String response = client.responseBody();
    
//     // 處理回應
//     if(statusCode > 0){
//       Serial.print("HTTP 回應碼: ");
//       Serial.println(statusCode);
//       Serial.print("回應內容: ");
//       Serial.println(response);
//     }
//     else{
//       Serial.print("發送 POST 請求失敗，錯誤碼: ");
//       Serial.println(statusCode);
//     }


//   delay(5000);
// }