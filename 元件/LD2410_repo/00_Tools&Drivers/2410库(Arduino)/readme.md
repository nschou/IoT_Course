# HLK-LD2410配置库使用介绍

## 初始化

### 提供两种初始化方式

```C++
HLKModuleConfig(HardwareSerial &serial);                              // 直接与模块通信的构造函数
HLKModuleConfig(HardwareSerial &serial, SoftwareSerial &debugSerial); // 增加调试口的构造函数
```

### 初始化示例

需要传入单片机连接模块的串口，调试串口可以选

```C++
// 带有调试串口的初始化
HLKModuleConfig hlk_config(hardwareSerial, debugSerial);
// 直接连接模块的初始化
HLKModuleConfig hlk_config(hardwareSerial);
```



### 雷达状态的初始化

结构体 `RadarStatus_2410` 是为雷达2410版本设计的，其中包含了以下信息:

- **targetStatus**: 描述雷达的目标状态，它是一个枚举值，可以为 `NoTarget`、`MovingTarget`、`StaticTarget`、`BothTargets` 或 `ErrorFrame`。
- **distance**: 表示雷达的目标距离，单位为毫米。
- **moveSetDistance** 和 **staticSetDistance**: 雷达的运动/静止探测距离门数量。
- **detectionDistance**: 雷达的最远探测距离门。
- **resolution**: 雷达的距离门分辨率。
- **noTargrtduration**: 无人持续时间。
- **radarMode_2410**: 表示模块的模式，例如基本上报模式或工程上报模式。
- **radarMovePower** 和 **radarStaticPower**: 结构体，分别包含运动能量值和静止能量值。
- **photosensitive**: 光敏值，范围为 0-255。

初始化示例

```c++
HLKModuleConfig::RadarStatus_2410 radarStatus;
```



### 如何获取雷达感应信息

可以使用`getStatus_2410()`方法来获取雷达状态，**(为了保证获取成功，可以加入重试机制)**

#### 示例代码

```C++
HLKModuleConfig::RadarStatus_2410 radarStatus;
int retryCount = 0;
const int MAX_RETRIES = 10;  // 最大重试次数，防止无限循环
do {
	radarStatus = hlk_config.getStatus_2410();
    retryCount++;
} while (radarStatus.distance == -1 && retryCount < MAX_RETRIES);//这段代码的目的是从hlk_config对象中重复获取雷达状态，直到雷达的距离不再为-1或直到达到最大重试次数MAX_RETRIES。
```



### 如何使用获取到的雷达信息

主要用到的就是雷达的状态信息和雷达探测的距离。

#### 示例代码

```C++
if (radarStatus.distance != -1) {// 避免打印无效数据
    debugSerial.print("Status: " + String(targetStatusToString(radarStatus.targetStatus)) + "  ----   ");// 打印状态
    debugSerial.println("Distance: " + String(radarStatus.distance) + "  Mode: " + String(radarStatus.radarMode_2410));	//打印距离和是否在工程模式
    debugSerial.print("Move: ");
    if (radarStatus.radarMode_2410 == 1) {// 如果在工程模式下就打印能量值信息
    	for (int i = 0; i < 9; i++) {
        	debugSerial.print(String(radarStatus.radarMovePower.moveGate[i]) + "  ,");
      	}
      	debugSerial.println("");
      	debugSerial.print("Static: ");
      	for (int i = 0; i < 9; i++) {
        	debugSerial.print(String(radarStatus.radarStaticPower.staticGate[i]) + "  ,");
      	}
      	debugSerial.println("");
        // 打印光敏信息
      	debugSerial.println("Photosensitive: " + String(radarStatus.photosensitive));
    }
}

// 用来解析雷达状态
const char* targetStatusToString(HLKModuleConfig::TargetStatus_2410 status) {
  switch (status) {
    case HLKModuleConfig::TargetStatus_2410::NoTarget:
      return "NoTarget";
    case HLKModuleConfig::TargetStatus_2410::MovingTarget:
      return "MovingTarget";
    case HLKModuleConfig::TargetStatus_2410::StaticTarget:
      return "StaticTarget";
    case HLKModuleConfig::TargetStatus_2410::BothTargets:
      return "BothTargets";
    default:
      return "Unknown";
  }
}
```

