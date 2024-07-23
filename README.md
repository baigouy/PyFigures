# PyFigures

Effortless creation of high-quality scientific figures in Python. 

[![Watch the video](./images/PyFigures.png)](https://youtu.be/sq7d1Aon4cQ)

Since a video is better than a thousand (click on the image above to view the demo). Or click here to access the complete [demo playlist](https://www.youtube.com/playlist?list=PLCtF2DKlhKYd6oz6qZPgA_WrD025q5Bl7).

**Note**: Most demo images are public domain and sourced from the [Cell Image Library](http://www.cellimagelibrary.org/).

# Installation

## 1. Conda Installation (Advanced Users)

For advanced users, we recommend installing the software using Conda. This will offer unlimited scripting capabilities.

### Prerequisites

- Install [Miniconda](https://docs.anaconda.com/miniconda/) if it is not already installed on your system.

### Installation Steps

Perform the following steps **only once** to set up your environment:

1. **Open a Command Prompt or Terminal.**

   - To open a **command prompt** on **Windows**, press **Windows+R** then type **cmd**.
   - To open a **command prompt** on **MacOS**, press **Command+Space** then type **Terminal**.
   - To open a **command prompt** on **Ubuntu**, press **Ctrl+Alt+T**.


2. **Create and activate a new Conda environment:**
   
    ```sh
    conda create -y -n PyFigures python==3.10.12
    conda activate PyFigures
    ```

3. **Upgrade pip:**
    
    ```sh
    pip install -U pip
    ```

4. **Install the `pyfigures` package:**
    
    ```sh
    pip install -U pyfigures
    ```
   
5. **Optional: Install additional dependencies for bioformats support:**
    
    ```sh
    pip install -U pyfigures[all]
    ```

6. **Run `pyfigures`:**
    
    ```sh
    python -m pyfigures
    ```
   
7. **Deactivate the Conda environment when you're done:**

    ```sh
    conda deactivate
    ```

### Run
   
   **Note:** The following steps need to be performed **only after** the software has been installed.
   
   Open a command prompt and type:

   ```sh
   conda activate PyFigures
   python -m pyfigures
   ```
   
   **Optional**: After running the software, you may deactivate the Conda environment if you wish:

   ```sh
   conda deactivate
   ```

## 2. Standalone Executable Installation (Easy)

Alternatively, you can install the software as a standalone executable. This does not require Conda and can be run on any system without the need for additional dependencies, but scripting capabilities will be limited to the bundled dependencies. 

- Windows **coming soon!** 
- MacOS **coming soon!**
- Linux **coming soon!**

## Troubleshooting Installation Issues

If you encounter **issues** related to installing the **python-javabridge** package, follow these steps:

1. Prerequisites for All Systems
   Before installing python-javabridge, ensure the following:

   - **Install OpenJDK 8**:

      - You need [OpenJDK 8](https://adoptium.net/temurin/releases/?version=8) installed on your system. Make sure it is added to your system's PATH environment variables (**JAVA_HOME** and **JDK_HOME**) so that it can be found by the installation process.

   - **Ensure a C Compiler is Available**:

      - The package requires a C compiler to build C extensions. Depending on your operating system, this will be different.

2. **Windows**-Specific Instructions

   If you are on Windows and encounter the error Microsoft Visual C++ 14.0 or greater is required, follow these steps to resolve it:

   - **Download the Build Tools**:
      - Visit the [Microsoft C++ Build Tools download page](https://visualstudio.microsoft.com/visual-cpp-build-tools/).

   - **Run the installer**.
     - During the installation process, **select the "Desktop development with C++" workload**.


   - Verify Installation:

      - Open a command prompt and run '**cl**'. If the command is recognized and provides output, the installation was successful.
   

   - **Retry Installation**:

       - After installing the build tools, try to install the python-javabridge package again:

         ```sh
         pip install python-javabridge
         ```

3. **MacOS and Linux**

   For MacOS and Linux systems, ensure you have the necessary build tools:

   - **MacOS**:
   
      Install Xcode Command Line Tools by running:
   
      ```sh
      xcode-select --install
      ```

   - **Linux**:

      Install build-essential (on Debian-based systems) or the equivalent development tools package for your distribution. For example, on Ubuntu, you can run:
      
      ```sh
      sudo apt-get install build-essential
      ```

   **After ensuring that a suitable compiler is available, retry the installation**:

      ```sh
      pip install python-javabridge
      ```

   By following these steps, you should be able to resolve issues and successfully install python-javabridge. If you continue to experience problems, consult the relevant documentation or seek support from the community
   
# Third party libraries

Below is a list of the 3<sup>rd</sup> party libraries used by PyFigures.<br><br> <font color='red'>**IMPORTANTLY: if you disagree with any license below, <u>please uninstall PyFigures</u>**.<br></font>

| Library name            | Use                                                         | Link                                          | License            |
|-------------------------|-------------------------------------------------------------|-----------------------------------------------|--------------------|
| **Markdown**            | Python implementation of Markdown                           | https://pypi.org/project/Markdown/            | BSD                |
| **matplotlib**          | Plots images and graphs                                     | https://pypi.org/project/matplotlib/          | PSF                |
| **numpy**               | Array/Image computing                                       | https://pypi.org/project/numpy/               | BSD                |
| **Pillow**              | Reads 'basic' images (.bmp, .png, .pnm, ...)                | https://pypi.org/project/Pillow/              | HPND               |
| **PyQt6**               | Graphical user interface (GUI)                              | https://pypi.org/project/PyQt6/               | GPL v3             |
| **QtPy**               | An abstraction layer for PyQt and PySide                    | https://pypi.org/project/QtPy/               | MIT             |
| **read-lif**            | Reads Leica .lif files                                      | https://pypi.org/project/read-lif/            | GPL v3             |
| **czifile**             | Reads Zeiss .czi files                                      | https://pypi.org/project/czifile/             | BSD (BSD-3-Clause) |
| **tifffile**            | Reads .tiff files (also reads Zeiss .lsm files)             | https://pypi.org/project/tifffile/            | BSD                |
| **python-bioformats**               | A library to open scientific images                         | https://pypi.org/project/python-bioformats/               | GPLv2                |
| **python-javabridge**               | A library to run java executables (required for bioformats) | https://pypi.org/project/python-javabridge/               | BSD                |
| **scikit-image**        | Image processing                                            | https://pypi.org/project/scikit-image/        | BSD (Modified BSD) |
| **scipy**               | Great library to work with numpy arrays                     | https://pypi.org/project/scipy/               | BSD                | 
| **scikit-learn**               | Great library for machine learning                          | https://pypi.org/project/scikit-learn/               | BSD                | 
| **tqdm**                | Command line progress                                       | https://pypi.org/project/tqdm/                | MIT, MPL 2.0       |
| **natsort**             | 'Human' like sorting of strings                             | https://pypi.org/project/natsort/             | MIT                |
| **numexpr**             | Speeds up image math                                        | https://pypi.org/project/numexpr/             | MIT                |
| **urllib3**             | Model architecture and trained models download              | https://pypi.org/project/urllib3/             | MIT                |
| **qtawesome**           | Elegant icons for PyQT/PySide                                       | https://pypi.org/project/QtAwesome/           | MIT                |
| **pandas**              | Data analysis toolkit                                       | https://pypi.org/project/pandas/              | BSD (BSD-3-Clause) |
| **numba**               | GPU acceleration of numpy ops                               | https://pypi.org/project/numba/               | BSD                |
| **roifile**               | A library to read ImageJ ROIs                               | https://pypi.org/project/roifile/               | BSD 3-Clause                |

# Other Figure-Making Software

[FigureJ](https://imagej.net/plugins/figurej)

[ScientiFig](https://imagej.github.io/list-of-update-sites/)

[omero.figure](https://www.openmicroscopy.org/omero/figure/)

[EzFig](https://imagej.github.io/list-of-update-sites/)

[QuickFigures](https://github.com/grishkam/QuickFigures)