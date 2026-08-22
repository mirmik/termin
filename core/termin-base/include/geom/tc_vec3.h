/// @file tc_vec3.h
/// @brief 3D вектор и операции над ним

#ifndef TC_VEC3_H
#define TC_VEC3_H

#include <math.h>
#include <stddef.h>
#include <tcbase/tc_types.h>

// C/C++ compatible struct initialization
#ifdef __cplusplus
#define TC_VEC3(x, y, z)                                                                                               \
    tc_vec3 {                                                                                                          \
        x, y, z                                                                                                        \
    }
#else
#define TC_VEC3(x, y, z)                                                                                               \
    (tc_vec3) {                                                                                                        \
        x, y, z                                                                                                        \
    }
#endif

#ifdef __cplusplus
extern "C" {
#endif

/// @name Конструкторы
/// @{

/// Создаёт вектор с заданными компонентами
/// @param x Компонента X
/// @param y Компонента Y
/// @param z Компонента Z
/// @return Новый вектор (x, y, z)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_new(double x, double y, double z) {
    return TC_VEC3(x, y, z);
}

/// Создаёт нулевой вектор (0, 0, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_zero(void) {
    return TC_VEC3(0, 0, 0);
}

/// Создаёт единичный вектор (1, 1, 1)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_one(void) {
    return TC_VEC3(1, 1, 1);
}

/// Единичный вектор оси X (1, 0, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_unit_x(void) {
    return TC_VEC3(1, 0, 0);
}

/// Единичный вектор оси Y (0, 1, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_unit_y(void) {
    return TC_VEC3(0, 1, 0);
}

/// Единичный вектор оси Z (0, 0, 1)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_unit_z(void) {
    return TC_VEC3(0, 0, 1);
}

/// Направление вправо в Termin: +X (1, 0, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_right(void) {
    return tc_vec3_unit_x();
}

/// Направление влево в Termin: -X (-1, 0, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_left(void) {
    return TC_VEC3(-1, 0, 0);
}

/// Направление вперёд в Termin: +Y (0, 1, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_forward(void) {
    return tc_vec3_unit_y();
}

/// Направление назад в Termin: -Y (0, -1, 0)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_backward(void) {
    return TC_VEC3(0, -1, 0);
}

/// Направление вверх в Termin: +Z (0, 0, 1)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_up(void) {
    return tc_vec3_unit_z();
}

/// Направление вниз в Termin: -Z (0, 0, -1)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_down(void) {
    return TC_VEC3(0, 0, -1);
}

TC_C_STATIC_INLINE tc_vec3f tc_vec3_to_float(tc_vec3 v) {
    tc_vec3f result = {(float)v.x, (float)v.y, (float)v.z};
    return result;
}

/// @}

/// @name Арифметика
/// @{

/// Покомпонентное сложение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a + b
TC_C_STATIC_INLINE tc_vec3 tc_vec3_add(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x + b.x, a.y + b.y, a.z + b.z);
}

/// Покомпонентное вычитание векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a - b
TC_C_STATIC_INLINE tc_vec3 tc_vec3_sub(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x - b.x, a.y - b.y, a.z - b.z);
}

/// Покомпонентное умножение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return (a.x*b.x, a.y*b.y, a.z*b.z)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_mul(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x * b.x, a.y * b.y, a.z * b.z);
}

/// Покомпонентное деление векторов
/// @param a Первый вектор
/// @param b Второй вектор (компоненты не должны быть нулевыми)
/// @return (a.x/b.x, a.y/b.y, a.z/b.z)
TC_C_STATIC_INLINE tc_vec3 tc_vec3_div(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x / b.x, a.y / b.y, a.z / b.z);
}

/// Умножение вектора на скаляр
/// @param v Вектор
/// @param s Скаляр
/// @return v * s
TC_C_STATIC_INLINE tc_vec3 tc_vec3_scale(tc_vec3 v, double s) {
    return TC_VEC3(v.x * s, v.y * s, v.z * s);
}

/// Инвертирует вектор
/// @param v Вектор
/// @return -v
TC_C_STATIC_INLINE tc_vec3 tc_vec3_neg(tc_vec3 v) {
    return TC_VEC3(-v.x, -v.y, -v.z);
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3_min(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(fmin(a.x, b.x), fmin(a.y, b.y), fmin(a.z, b.z));
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3_max(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(fmax(a.x, b.x), fmax(a.y, b.y), fmax(a.z, b.z));
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3_clamp(tc_vec3 v, tc_vec3 minimum, tc_vec3 maximum) {
    return TC_VEC3(fmin(fmax(v.x, minimum.x), maximum.x),
                   fmin(fmax(v.y, minimum.y), maximum.y),
                   fmin(fmax(v.z, minimum.z), maximum.z));
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3_abs(tc_vec3 v) {
    return TC_VEC3(fabs(v.x), fabs(v.y), fabs(v.z));
}

TC_C_STATIC_INLINE double tc_vec3_min_component(tc_vec3 v) {
    return fmin(v.x, fmin(v.y, v.z));
}

TC_C_STATIC_INLINE double tc_vec3_max_component(tc_vec3 v) {
    return fmax(v.x, fmax(v.y, v.z));
}

/// @}

/// @name Произведения
/// @{

/// Скалярное произведение
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a · b
TC_C_STATIC_INLINE double tc_vec3_dot(tc_vec3 a, tc_vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

/// Векторное произведение
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a × b
TC_C_STATIC_INLINE tc_vec3 tc_vec3_cross(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

/// @}

/// @name Длина и нормализация
/// @{

/// Квадрат длины вектора
/// @param v Вектор
/// @return |v|²
TC_C_STATIC_INLINE double tc_vec3_length_sq(tc_vec3 v) {
    return v.x * v.x + v.y * v.y + v.z * v.z;
}

/// Длина вектора
/// @param v Вектор
/// @return |v|
TC_C_STATIC_INLINE double tc_vec3_length(tc_vec3 v) {
    return sqrt(tc_vec3_length_sq(v));
}

TC_C_STATIC_INLINE bool tc_vec3_is_finite(tc_vec3 v) {
    return isfinite(v.x) && isfinite(v.y) && isfinite(v.z);
}

TC_C_STATIC_INLINE bool tc_vec3_try_normalized(tc_vec3 v, double epsilon, tc_vec3* out_normalized) {
    double length = hypot(hypot(v.x, v.y), v.z);
    if (out_normalized == NULL || !tc_vec3_is_finite(v) || !isfinite(length) || !isfinite(epsilon) || epsilon < 0.0 ||
        length <= epsilon) {
        return false;
    }
    *out_normalized = tc_vec3_scale(v, 1.0 / length);
    return true;
}

TC_C_STATIC_INLINE tc_vec3 tc_vec3_normalized_or(tc_vec3 v, tc_vec3 fallback, double epsilon) {
    tc_vec3 result;
    return tc_vec3_try_normalized(v, epsilon, &result) ? result : fallback;
}

/// Нормализует вектор
/// @param v Вектор
/// @return Единичный вектор того же направления, или (0,0,0) если |v| ≈ 0
TC_C_STATIC_INLINE tc_vec3 tc_vec3_normalize(tc_vec3 v) {
    double len = tc_vec3_length(v);
    if (len < 1e-12)
        return tc_vec3_zero();
    return tc_vec3_scale(v, 1.0 / len);
}

/// Расстояние между двумя точками
/// @param a Первая точка
/// @param b Вторая точка
/// @return |a - b|
TC_C_STATIC_INLINE double tc_vec3_distance(tc_vec3 a, tc_vec3 b) {
    return tc_vec3_length(tc_vec3_sub(a, b));
}

/// @}

/// @name Интерполяция
/// @{

/// Линейная интерполяция между векторами
/// @param a Начальный вектор (t=0)
/// @param b Конечный вектор (t=1)
/// @param t Параметр интерполяции [0, 1]
/// @return a + (b - a) * t
TC_C_STATIC_INLINE tc_vec3 tc_vec3_lerp(tc_vec3 a, tc_vec3 b, double t) {
    return TC_VEC3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t);
}

/// @}

/// @name Сравнение
/// @{

/// Точное сравнение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return true если все компоненты равны
TC_C_STATIC_INLINE bool tc_vec3_eq(tc_vec3 a, tc_vec3 b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}

/// Приближённое сравнение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @param eps Допустимая погрешность
/// @return true если |a.x - b.x| < eps для всех компонент
TC_C_STATIC_INLINE bool tc_vec3_near(tc_vec3 a, tc_vec3 b, double eps) {
    return fabs(a.x - b.x) < eps && fabs(a.y - b.y) < eps && fabs(a.z - b.z) < eps;
}

/// @}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC3_H
