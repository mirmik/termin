#ifndef TC_LOG_H
#define TC_LOG_H

/// @file tc_log.h
/// @brief Система логирования Termin

// TC_LOG_API is dllexport when building termin_core (TC_EXPORTS) or entity_lib (ENTITY_LIB_EXPORTS)
#ifdef _WIN32
    #if defined(TC_EXPORTS) || defined(ENTITY_LIB_EXPORTS)
        #define TC_LOG_API __declspec(dllexport)
    #else
        #define TC_LOG_API __declspec(dllimport)
    #endif
#else
    #define TC_LOG_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/// Уровни логирования
typedef enum {
    TC_LOG_DEBUG = 0,  ///< Отладочные сообщения
    TC_LOG_INFO = 1,   ///< Информационные сообщения
    TC_LOG_WARN = 2,   ///< Предупреждения
    TC_LOG_ERROR = 3   ///< Ошибки
} tc_log_level;

/// Callback для перехвата логов
/// @param level Уровень сообщения
/// @param message Текст сообщения
typedef void (*tc_log_callback)(tc_log_level level, const char* message);

/// Устанавливает callback для перехвата логов (например, для консоли редактора)
/// @param callback Функция-обработчик или NULL для сброса
TC_LOG_API void tc_log_set_callback(tc_log_callback callback);

/// Устанавливает минимальный уровень логирования
/// @param min_level Сообщения ниже этого уровня будут игнорироваться
TC_LOG_API void tc_log_set_level(tc_log_level min_level);

/// Выводит сообщение с указанным уровнем
/// @param level Уровень сообщения
/// @param format Строка формата (printf-style)
TC_LOG_API void tc_log(tc_log_level level, const char* format, ...);

/// Выводит отладочное сообщение
/// @param format Строка формата (printf-style)
TC_LOG_API void tc_log_debug(const char* format, ...);

/// Выводит информационное сообщение
/// @param format Строка формата (printf-style)
TC_LOG_API void tc_log_info(const char* format, ...);

/// Выводит предупреждение
/// @param format Строка формата (printf-style)
TC_LOG_API void tc_log_warn(const char* format, ...);

/// Выводит сообщение об ошибке
/// @param format Строка формата (printf-style)
TC_LOG_API void tc_log_error(const char* format, ...);

#ifdef __cplusplus
}
#endif

#endif // TC_LOG_H
