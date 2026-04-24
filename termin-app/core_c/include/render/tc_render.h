#ifndef TC_RENDER_H
#define TC_RENDER_H

// render engine

// Выполняет пайплайн (не выводит изображение. работает на уровне промежуточных fbo и собственных fbo viewport-ов)
void tc_render_framegraph_exec(tc_framegraph* framegraph, tc_scene_handle scene);

// Переносит изображение из viewport fbos на surface 
void tc_render_present_display(tc_display* display);

#endif
