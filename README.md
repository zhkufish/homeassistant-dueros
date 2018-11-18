# HomeAssistant-Dueros
HomeAssistant 小度智能音箱插件


原理上跟天猫精灵接入是一样的, 但是小度的好处是可以自定义名称.

我目前使用的是HomeAsisstant 0.81.6的版本, 其它版本我没有测试.

------------------------------------

一.  首先, 保证homeassistant可以外网访问,  并且支持https
====================================

授权的过程遇到了个坑, 不知道是不什么原因, 直接用ha的8123默认端口, 一直授权失败. 后来配置了nginx做转发才授权成功. 如果有人遇到同样的问题的话, 我再把nginx的配置发上来吧. 如果出现授权失败的话, 可以尝试以下方法
ps: 用群晖的朋友可以尝试这个办法(https://bbs.hassbian.com/forum.php?mod=viewthread&tid=5417&page=5#pid155731)

```
1.安装nginx web服务器 (约6MB)

sudo apt-get install nginx -y

2.修改nginx的配置文件

sudo nano /etc/nginx/sites-available/default

把配置修改一下. 把{}里面的内容替换为你自己的信息

server {
  listen 38123;
  listen 443 ssl http2;
  ssl_certificate {这里要填ssl证书路径};
  ssl_certificate_key {这里要填ssl的私钥路径};
  ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
  ssl_ciphers EECDH+CHACHA20:EECDH+AES128:RSA+AES128:EECDH+AES256:RSA+AES256:EECDH+3DES:RSA+3DES:!MD5;
  ssl_prefer_server_ciphers on;
  ssl_session_timeout 10m;
  ssl_session_cache builtin:1000 shared:SSL:10m;
  ssl_buffer_size 1400;
  add_header Strict-Transport-Security max-age=15768000;
  ssl_stapling on;
  ssl_stapling_verify on;
  server_name {你的域名};
  access_log /var/log/nginx/{你的域名}_nginx.log combined;
  error_log /var/log/nginx/{你的域名}_nginx.error.log debug;
  index index.html index.htm index.php;
  if ($ssl_protocol = "") { return 301 https://$host$request_uri; }
  
  #error_page 404 /404.html;
  #error_page 502 /502.html;
  charset utf-8; #默认编码方式
  client_max_body_size 75M;

  # 其他的请求全部交给Python的uWSGI来处理
  location / {
      proxy_pass https://127.0.0.1:8123;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $connection_upgrade;
  }
}

然后执行 nginx -s reload
试一下在浏览器, 输入https://{你的域名} , 看看能否访问. 注意不需要带上端口了
```

```
https证书申请, 下面有3个链接, 3个不同的方法. 大家看哪个合适自己吧
https://bbs.hassbian.com/thread-4758-1-1.html
https://bbs.hassbian.com/thread-2980-1-1.html
https://blog.csdn.net/conghua19/article/details/81433716
```


二. 百度dueros后台配置
====================================
![](https://github.com/zhkufish/homeassistant-dueros/raw/master/readme_pic1.png)


三. 添加自定义插件：
====================================
```
把文件dueros.py 放到/config/custom_components目录下面
```

四. configuration.yaml 文件配置
====================================
```
dueros:
  expire_hours: 180  #授权过期时间. 该参数不是必填
```

五. 一些其它配置
====================================
必须 要有friendly_name(在customize.yaml里面), 否则可能会发现不了,
```
switch.light:  
    friendly_name: 客厅灯  
    dueros_hidden: true   #如果不想小度添加某个设备,可以配置该参数
```

六. 目前已经测试可用功能
====================================
1. 开关指令
2. 灯的颜色, 亮度 指令
3. 小米扫地机器人, 支持调整吸力强度(标准档和强劲档)
4. 窗帘 (只支持开和关, 不支持开到指定位置)

七. 待完善功能:
====================================
1. 延时指令功能(小度支持 5分钟后关灯 指令, 但是指令到homeassistant之后, 我不知道要怎么实现, 期待有大神指点一下)
2. 传感器查询指令有问题, (目前温度, 湿度等传感器的数据还无法识别)



