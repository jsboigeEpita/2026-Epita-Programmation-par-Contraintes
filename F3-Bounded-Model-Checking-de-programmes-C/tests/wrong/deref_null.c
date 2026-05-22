int main() {
    int a;
    int *p;

    if (a == 0) {
        a = *p;
    } else {
        p = &a;
        a = *p;
    }

    return a;
}