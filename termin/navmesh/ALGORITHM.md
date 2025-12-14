# NavMesh Polygon Building Algorithm

## Шаг 1: Сбор поверхностных вокселей

**Вход:** VoxelGrid с surface_normals (dict: coord → normal)

**Выход:** dict `{(vx, vy, vz): normal}` — только воксели с нормалями

---

## Шаг 2: Region Growing

**Вход:** dict `{(vx, vy, vz): normal}`

**Алгоритм:** BFS — берём seed, добавляем соседей если `dot(seed_normal, neighbor_normal) > threshold`

**Выход:** list of `(list[coord], avg_normal)` — группы вокселей с усреднённой нормалью

---

## Шаг 3: Вычислить плоскость для группы

**Вход:** `list[coord]` — координаты вокселей группы, `avg_normal`

**Алгоритм:**
- Переводим coord в мировые координаты центров вокселей
- Вычисляем центроид (среднее)
- Плоскость: точка = центроид, нормаль = avg_normal

**Выход:** `(plane_point, plane_normal)` — плоскость

---

## Шаг 4: Проецируем центры на плоскость

**Вход:** центры вокселей (3D), плоскость

**Алгоритм:** `projected = point - dot(point - plane_point, normal) * normal`

**Выход:** list of 3D точек на плоскости

---

## Шаг 5: Переводим в 2D

**Вход:** 3D точки на плоскости, normal

**Алгоритм:** строим ортонормированный базис (u, v) перпендикулярный normal, проецируем

**Выход:** list of 2D точек `(u, v)`, базис `(origin, u, v)` для обратного преобразования

---

## Шаг 6: Alpha Shape (Delaunay + фильтрация)

**Вход:** list of 2D точек, alpha = cell_size * 0.8

**Алгоритм:**
1. Delaunay триангуляция (scipy.spatial.Delaunay)
2. Для каждого треугольника вычисляем circumradius: `R = (a * b * c) / (4 * area)`
3. Оставляем треугольники где `circumradius <= alpha`

**Выход:**
- Треугольники (индексы вершин)
- Boundary edges (рёбра, принадлежащие одному треугольнику) — для будущего использования

---

## Шаг 7: Обратно в 3D

**Вход:** 2D вершины, треугольники, базис `(origin, u, v)`

**Алгоритм:** `3D = origin + u_coord * basis_u + v_coord * basis_v`

**Выход:** NavPolygon с vertices (3D), triangles, normal

---

## TODO (потом)

- [ ] Douglas-Peucker для упрощения boundary
- [ ] Сшивание соседних полигонов (общие вершины)
- [ ] Перенос Delaunay на C++
