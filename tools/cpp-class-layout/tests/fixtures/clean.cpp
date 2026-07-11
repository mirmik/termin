#include <cstddef>
#include <vector>

class CleanModel {
  private:
    enum class State { Idle, Ready };
    using Values = std::vector<int>;

    static inline size_t instance_count_ = 0;
    State state_ = State::Idle;
    Values values_;

  public:
    CleanModel() = default;
    size_t size() const;

    template<typename Value>
    void append(Value value);

  private:
    void notify();
};

struct CleanValue {
    int value = 0;
    unsigned flags : 4 = 0;

    bool empty() const;
};

class FriendBeforeMethod {
  private:
    int value_ = 0;

    friend void inspect(const FriendBeforeMethod& value);

  public:
    int value() const;
};

template<typename Value>
class CleanTemplate {
  private:
    Value value_{};

  public:
    const Value& value() const;
};
