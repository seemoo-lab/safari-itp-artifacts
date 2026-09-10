# Custom WebKit
This repository contains patches for enhanced logging for WebKit's Intelligent Tracking Prevention (ITP) and Advanced Tracking and Fingerprint Protection (ATFP) features.

## Setup
1. Clone the official WebKit repository:
```bash
git clone https://github.com/WebKit/WebKit.git
```
2. Apply the patches from the `diff.patch` file:
```bash
cd WebKit
git apply /path/to/diff.patch
```
3. Build WebKit according to the official instructions: [WebKit Build Instructions](https://github.com/WebKit/WebKit#building-webkit).

