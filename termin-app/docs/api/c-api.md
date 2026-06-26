# C API Reference

Низкоуровневый C API библиотеки Termin теперь живёт в SDK-модулях-владельцах, а не в `termin-app/core_c`.

## Логирование (tc_log.h)

Заголовочный файл: `termin-base/include/tcbase/tc_log.h`

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

Заголовочный файл: `termin-base/include/geom/tc_vec3.h`

Полная документация C API находится в публичных заголовках соответствующих SDK-модулей.
