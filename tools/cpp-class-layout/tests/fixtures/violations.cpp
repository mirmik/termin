class FieldsAtBottom {
  public:
    void update();

  private:
    int value_ = 0;
    static inline int revision_ = 1;
};

class FieldAfterConstructor {
  public:
    FieldAfterConstructor() = default;

  private:
    int value_ = 0;
};

struct FieldAfterFunctionTemplate {
    template<typename Value>
    void set(Value value);

    int value = 0;
};

class AccessSectionDoesNotResetOrder {
  private:
    int first_ = 0;

  public:
    void update();

  protected:
    int second_ = 0;
};

class AnonymousUnionAfterMethod {
  public:
    void reset();

  private:
    union {
        int integer_value_;
        float float_value_;
    };
};

template<typename Value>
class FieldAtBottomInTemplate {
  public:
    const Value& value() const;

  private:
    Value value_{};
};

#define TERMIN_TEST_FIELD int macro_field_ = 0

class MacroFieldAfterMethod {
  public:
    void update();

  private:
    TERMIN_TEST_FIELD;
};
