#include <TinyGPS++.h>
#include <SoftwareSerial.h>
#include <WiFi.h>

/*
   This sample sketch demonstrates the normal use of a TinyGPS++ (TinyGPSPlus) object.
   It requires the use of SoftwareSerial, and assumes that you have a
   4800-baud serial GPS device hooked up on pins 4(rx) and 3(tx).
*/

const char* ssid = "af";          // 替換為您的 WiFi 名稱
const char* password = "icanlabst333";      // 替換為您的 WiFi 密碼

const char* serverAddress = "172.24.16.12"; // 伺服器地址（不含 http://）
int port = 5001; // HTTP 為 80，HTTPS 為 443

static const int TXPin = 4, RXPin = 3;
static const uint32_t GPSBaud = 9600;

// The TinyGPS++ object
TinyGPSPlus gps;

// The serial connection to the GPS device
SoftwareSerial ss(RXPin, TXPin);

String lat = "0.0", lon = "0.0", s = "";
int delay_time = 1000;

void setup()
{
  Serial.begin(115200);

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Attempting to connect to WiFi network: ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    delay(5000);
  }
  Serial.println("Wifi connected.");

  ss.begin(GPSBaud);

  Serial.println(F("DeviceExample.ino"));
  Serial.println(F("A simple demonstration of TinyGPS++ with an attached GPS module"));
  Serial.print(F("Testing TinyGPS++ library v. ")); Serial.println(TinyGPSPlus::libraryVersion());
  Serial.println(F("by Mikal Hart"));
  Serial.println();
}

void loop()
{
  // This sketch displays information every time a new sentence is correctly encoded.
  while (ss.available() > 0)
    if (gps.encode(ss.read())) {
      process_Info();
      delay(delay_time);  // 單位為毫秒（milliseconds），1000 ms = 1 秒
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
  if (gps.location.isValid())
  {
    lat = String(gps.location.lat(), 4);
    lon = String(gps.location.lng(), 4);
  }
  else
  {
    lat = "120.6001";
    lon = "24.1790";
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