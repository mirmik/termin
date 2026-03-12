# Граф зависимостей библиотек

Ниже показан текущий граф зависимостей между основными C/C++ библиотеками монорепозитория.

- Стрелка `A -> B` означает: `B` напрямую зависит от `A`.
- Транзитивные зависимости скрыты, чтобы граф оставался читаемым.
- Граф отражает верхнеуровневые package-зависимости из `CMakeLists.txt`, а не каждый внутренний target.
- Source of truth для картинки: [library-dependencies.dot](./library-dependencies.dot)
- Открыть SVG отдельно: [library-dependencies.svg](./library-dependencies.svg)

<object
  data="./library-dependencies.svg"
  type="image/svg+xml"
  style="width: 100%; min-height: 70vh; border: 1px solid #ddd;"
>
  <a href="./library-dependencies.svg">Открыть граф зависимостей в полном размере</a>
</object>
