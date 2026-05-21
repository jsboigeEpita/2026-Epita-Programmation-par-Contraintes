int main() {
    int a = 1;
    int *p;

    if (a == 0) {
        a = *p;
    } else {
        p = &a;
        a = *p;
    }

    return a;
}