# C API Reference

Низкоуровневый C API библиотеки Termin.

## Логирование (tc_log.h)

Заголовочный файл: `core_c/include/tc_log.h`

```c
// Уровни логирования
TC_LOG_DEBUG
TC_LOG_INFO
TC_LOG_WARN
TC_LOG_ERROR

// Основная функция
void tc_log(int level, const char* fmt, ...);
```

## 3D Вектор (tc_vec3.h)

Заголовочный файл: `core_c/include/geom/tc_vec3.h`

Полная документация C API находится в заголовочных файлах `core_c/include/`.
