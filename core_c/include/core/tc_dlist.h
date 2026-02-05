#ifndef TC_DLIST_H
#define TC_DLIST_H

// Intrusive doubly-linked list implementation (based on Linux kernel list.h)
//
// Key property: unlinked nodes have next == prev == self, so unlinking
// an already-unlinked node is safe (no-op).
//
// Usage:
//   struct my_item {
//       int data;
//       tc_dlist_node node;  // embed in your struct
//   };
//
//   tc_dlist_head list;
//   tc_dlist_init_head(&list);
//
//   struct my_item item;
//   tc_dlist_init_node(&item.node);
//   tc_dlist_add_tail(&item.node, &list);
//
//   tc_dlist_for_each_entry(pos, &list, my_item, node) {
//       // use pos->data
//   }

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Node structure (embed in your data structures)
typedef struct tc_dlist_node {
    struct tc_dlist_node *next;
    struct tc_dlist_node *prev;
} tc_dlist_node;

// Head structure (same as node, but semantically different)
typedef tc_dlist_node tc_dlist_head;

// Static initializer for head (points to itself)
#define TC_DLIST_HEAD_INIT(name) { &(name), &(name) }

// Declare and initialize a list head
#define TC_DLIST_HEAD(name) tc_dlist_head name = TC_DLIST_HEAD_INIT(name)

// Get containing structure from node pointer
#define tc_dlist_entry(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))

// Initialize a list head (empty list)
static inline void tc_dlist_init_head(tc_dlist_head *head) {
    head->next = head;
    head->prev = head;
}

// Initialize a node (unlinked state: points to itself)
static inline void tc_dlist_init_node(tc_dlist_node *node) {
    node->next = node;
    node->prev = node;
}

// Check if node is linked to a list (not pointing to itself)
static inline bool tc_dlist_is_linked(const tc_dlist_node *node) {
    return node->next != node;
}

// Check if list is empty
static inline bool tc_dlist_empty(const tc_dlist_head *head) {
    return head->next == head;
}

// Internal: insert node between prev and next
static inline void tc_dlist__add(tc_dlist_node *node,
                                  tc_dlist_node *prev,
                                  tc_dlist_node *next) {
    node->prev = prev;
    node->next = next;
    next->prev = node;
    prev->next = node;
}

// Add node after head (at front of list)
static inline void tc_dlist_add(tc_dlist_node *node, tc_dlist_head *head) {
    tc_dlist__add(node, head, head->next);
}

// Add node before head (at end of list)
static inline void tc_dlist_add_tail(tc_dlist_node *node, tc_dlist_head *head) {
    tc_dlist__add(node, head->prev, head);
}

// Internal: remove node by connecting prev and next
static inline void tc_dlist__del(tc_dlist_node *prev, tc_dlist_node *next) {
    next->prev = prev;
    prev->next = next;
}

// Remove node from list and reinitialize (safe to call multiple times)
static inline void tc_dlist_del(tc_dlist_node *node) {
    if (node->next != node) {
        tc_dlist__del(node->prev, node->next);
        tc_dlist_init_node(node);
    }
}

// Remove from one list and add to front of another
static inline void tc_dlist_move(tc_dlist_node *node, tc_dlist_head *head) {
    tc_dlist__del(node->prev, node->next);
    tc_dlist_add(node, head);
}

// Remove from one list and add to end of another
static inline void tc_dlist_move_tail(tc_dlist_node *node, tc_dlist_head *head) {
    tc_dlist__del(node->prev, node->next);
    tc_dlist_add_tail(node, head);
}

// Get first entry (or NULL if empty)
#define tc_dlist_first_entry(head, type, member) \
    (tc_dlist_empty(head) ? NULL : tc_dlist_entry((head)->next, type, member))

// Get last entry (or NULL if empty)
#define tc_dlist_last_entry(head, type, member) \
    (tc_dlist_empty(head) ? NULL : tc_dlist_entry((head)->prev, type, member))

// Get next entry
#define tc_dlist_next_entry(pos, type, member) \
    tc_dlist_entry((pos)->member.next, type, member)

// Get prev entry
#define tc_dlist_prev_entry(pos, type, member) \
    tc_dlist_entry((pos)->member.prev, type, member)

// Iterate over list nodes
#define tc_dlist_for_each(pos, head) \
    for (pos = (head)->next; pos != (head); pos = pos->next)

// Iterate over list nodes (safe for removal)
#define tc_dlist_for_each_safe(pos, tmp, head) \
    for (pos = (head)->next, tmp = pos->next; pos != (head); pos = tmp, tmp = pos->next)

// Iterate over list entries (C99 version - pos must be declared before)
#define tc_dlist_for_each_entry(pos, head, type, member) \
    for (pos = tc_dlist_entry((head)->next, type, member); \
         &pos->member != (head); \
         pos = tc_dlist_entry(pos->member.next, type, member))

// Iterate over list entries in reverse
#define tc_dlist_for_each_entry_reverse(pos, head, type, member) \
    for (pos = tc_dlist_entry((head)->prev, type, member); \
         &pos->member != (head); \
         pos = tc_dlist_entry(pos->member.prev, type, member))

// Iterate over list entries (safe for removal)
#define tc_dlist_for_each_entry_safe(pos, tmp, head, type, member) \
    for (pos = tc_dlist_entry((head)->next, type, member), \
         tmp = tc_dlist_entry(pos->member.next, type, member); \
         &pos->member != (head); \
         pos = tmp, tmp = tc_dlist_entry(tmp->member.next, type, member))

// Count entries in list
static inline size_t tc_dlist_size(const tc_dlist_head *head) {
    size_t count = 0;
    tc_dlist_node *pos;
    tc_dlist_for_each(pos, head) {
        count++;
    }
    return count;
}

// Check if node is in list
static inline bool tc_dlist_contains(const tc_dlist_head *head, const tc_dlist_node *node) {
    tc_dlist_node *pos;
    tc_dlist_for_each(pos, head) {
        if (pos == node) return true;
    }
    return false;
}

#ifdef __cplusplus
}
#endif

#endif // TC_DLIST_H
