%% notes.cls — document class for accessible course notes.
%%
%% scripts/init_project.py copies this to <latex_class>.cls and renames the
%% \ProvidesClass line to match, so the class name is the course's own.
%%
%% Produces a tagged PDF/UA-1 file from LuaLaTeX. The \DocumentMetadata line
%% that switches tagging on lives in each document's .tex file, because it must
%% precede \documentclass.
%%
%% Requires: lualatex, and a TeX Live new enough that tagpdf writes proper
%% alternative text for math. See BUILD.md.

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{notes}[2026/09/30 accessible course notes]

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt,letterpaper,oneside]{article}

% ---------------------------------------------------------------- packages
\RequirePackage{geometry}
\geometry{letterpaper,top=22mm,bottom=20mm,left=20mm,right=20mm,
          footskip=11mm}

\RequirePackage{unicode-math}
\setmainfont{Latin Modern Roman}
\setsansfont{Latin Modern Sans}
\setmonofont{Latin Modern Mono}
\setmathfont{Latin Modern Math}

\RequirePackage{amsmath}
\RequirePackage[makeroom]{cancel}   % crossed-out terms, as in the original
\RequirePackage{graphicx}
\RequirePackage{xcolor}
\RequirePackage{array}
\RequirePackage{longtable}
\RequirePackage{framed}
\RequirePackage{enumitem}
\RequirePackage{fancyhdr}
\RequirePackage{placeins}
\RequirePackage{ragged2e}
\RequirePackage{hyperref}

% ------------------------------------------------------------------ colours
% Carried over from the HTML build so the two look like one family.
\definecolor{nt@ink}   {HTML}{1A1A1A}
\definecolor{nt@accent}{HTML}{123A52}
\definecolor{nt@flag}  {HTML}{8C1017}
\definecolor{nt@rule}  {HTML}{C9C2B4}
\definecolor{nt@notebg}{HTML}{F4F1E8}
\definecolor{nt@probbg}{HTML}{F2F5F7}
\definecolor{nt@faint} {HTML}{4A4A4A}
\color{nt@ink}

% --------------------------------------------------------------- title block
% \docheading, \subtitleline and \runningfoot are set by the converter.
\newcommand{\nt@docheading}{}
\newcommand{\nt@subtitle}{}
\newcommand{\nt@runningfoot}{}
\newcommand{\docheading}[1]{\renewcommand{\nt@docheading}{#1}}
\newcommand{\subtitleline}[1]{\renewcommand{\nt@subtitle}{#1}}
\newcommand{\runningfoot}[1]{\renewcommand{\nt@runningfoot}{#1}}

\newcommand{\maketitlepage}{%
  \begingroup
    \raggedright
    {\sffamily\bfseries\color{nt@accent}\fontsize{20}{24}\selectfont
     \nt@docheading\par}
    \vskip 2pt
    {\color{nt@accent}\hrule height 1.6pt}
    \vskip 6pt
    {\sffamily\color{nt@faint}\fontsize{10}{13}\selectfont
     \nt@subtitle\par}
  \endgroup
  \vskip 18pt
}

% ----------------------------------------------------------------- headings
\renewcommand{\section}{\@startsection{section}{1}{0pt}%
  {-2.6ex \@plus -1ex \@minus -.2ex}{1.3ex \@plus .2ex}%
  {\normalfont\sffamily\bfseries\fontsize{14}{17}\selectfont\color{nt@accent}}}
\renewcommand{\subsection}{\@startsection{subsection}{2}{0pt}%
  {-2.2ex \@plus -1ex \@minus -.2ex}{1.0ex \@plus .2ex}%
  {\normalfont\sffamily\bfseries\fontsize{11.5}{14}\selectfont\color{nt@accent}}}
\renewcommand{\subsubsection}{\@startsection{subsubsection}{3}{0pt}%
  {-2.0ex \@plus -1ex \@minus -.2ex}{0.9ex \@plus .2ex}%
  {\normalfont\sffamily\bfseries\fontsize{11}{13}\selectfont\color{nt@accent}}}
\setcounter{secnumdepth}{0}

% A heading the original set in red. The colour is decorative only: the
% heading level already carries the meaning.
\newcommand{\flagsection}[1]{%
  {\let\nt@savedcolor\nt@accent
   \definecolor{nt@accent}{HTML}{8C1017}%
   \section{#1}%
   \definecolor{nt@accent}{HTML}{123A52}}}

% ------------------------------------------------------------------- footer
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
% The page total is the kernel's \PreviousTotalPages, which the .aux
% records at the very end of the run. A \label written by \AtEndDocument
% was used before, and it is lost when the text fills the last page to
% its foot: the label falls onto an empty page that is never shipped out,
% and the footer reads "page 1 of ??".
\fancyfoot[C]{\sffamily\fontsize{8.5}{10}\selectfont\color{nt@faint}%
  \nt@runningfoot{} — page \thepage{} of \PreviousTotalPages}

% ------------------------------------------------------------- shaded blocks
% framed's \FrameCommand is redefined per environment so each block gets its
% own background and left rule, and all of them break across pages.
\newlength{\nt@rulewd}\setlength{\nt@rulewd}{3pt}

\newcommand{\nt@framecmd}[2]{%
  \setlength{\fboxsep}{8pt}%
  \fcolorbox{#1}{#2}{\hspace{-4pt}%
    \textcolor{#1}{\vrule width \nt@rulewd}\hspace{6pt}%
    \normalcolor##1}}

\newenvironment{notebox}
  {\def\FrameCommand{\setlength{\fboxsep}{9pt}%
     \textcolor{nt@accent}{\vrule width \nt@rulewd}%
     \colorbox{nt@notebg}}%
   \MakeFramed{\advance\hsize-\width\FrameRestore}%
   \fontsize{10}{14}\selectfont}
  {\endMakeFramed}

\newenvironment{problembox}
  {\def\FrameCommand{\setlength{\fboxsep}{8pt}%
     \textcolor{nt@accent}{\vrule width \nt@rulewd}%
     \colorbox{nt@probbg}}%
   \MakeFramed{\advance\hsize-\width\FrameRestore}}
  {\endMakeFramed}

\newenvironment{quotebox}
  {\def\FrameCommand{\setlength{\fboxsep}{0pt}%
     \textcolor{nt@rule}{\vrule width 2pt}\hspace{9pt}}%
   \MakeFramed{\advance\hsize-\width\FrameRestore}}
  {\endMakeFramed}

% Content the original keeps together on one page.
\newenvironment{keepbox}{\par\begin{minipage}{\linewidth}}
  {\end{minipage}\par}

% A run of display equations, indented like the HTML build and kept together.
\newenvironment{eqblock}{\par\addvspace{4pt}\begingroup
  \abovedisplayskip=4pt \belowdisplayskip=4pt
  \abovedisplayshortskip=2pt \belowdisplayshortskip=2pt}
  {\endgroup\par\addvspace{5pt}}

% A display equation with a spoken alternative of its own.
%
% The tagging code tags every formula and attaches the LaTeX source as its
% alternative text, which reads aloud as "backslash frac". That is tolerable
% for a simple expression and useless for a matrix, a cancelled term or an
% integral whose limits are stacked, so those equations are wrapped in a
% Formula structure element carrying a written sentence instead.
%
% /Alt on a structure element replaces its whole subtree for assistive
% technology, so the sentence is what is read and the automatic tagging
% underneath it is not. \tagstructbegin is tagpdf's documented interface,
% rather than a patch of the math tagging internals, which move between
% releases.
\newcommand{\eqalt}[2]{%
  \tagstructbegin{tag=Formula,alt={#1}}%
  #2%
  \tagstructend}

% Original page boundaries.
\newcommand{\srcnote}[1]{%
  \par\addvspace{12pt}%
  {\color{nt@rule}\hrule height 0.5pt}%
  \vskip 3pt
  {\sffamily\fontsize{8.5}{11}\selectfont\color{nt@faint}#1\par}%
  \addvspace{4pt}}

% ------------------------------------------------------------------ captions
% LaTeX numbers the figures, and the converter removes the "Figure N." that
% the transcription had written into the caption text, so the number appears
% once. The figures are converted in the order they were written, so the
% numbers still match every "see Figure N" in the prose.
%
% The caption package is deliberately not loaded, \@makecaption is not
% redefined, and \caption* is not used: the tagging code supplies its own
% caption handling, which quietly ignores the first two and prints a literal
% asterisk for the third. Styling the caption's own content is what actually
% takes effect.
\setlength{\abovecaptionskip}{8pt}
\setlength{\belowcaptionskip}{0pt}
%
% Captions are set flush left and ragged right, however long, which reads more
% easily than justified or centred text (WCAG 1.4.8 advises against justified
% text). Two things stand in the way, and each is dealt with here rather than
% by redefining the caption code, for the reason above.
%
%  * The caption routine centres a caption that fits on one line. It decides
%    by measuring the label and text in a box, so the trailing \hspace makes
%    every caption measure wider than the line and take the paragraph branch.
%    The space costs nothing there: TeX discards glue that ends a paragraph.
%  * The paragraph branch sets "label: text\par", and line breaking uses the
%    settings in force at that \par. The text is therefore not wrapped in a
%    group of its own, so \RaggedRight is still in effect when the paragraph
%    ends. Wrapped in braces, as it once was, the setting lapsed before the
%    \par and the caption came out justified, with the stretch piling up in
%    the space after "Figure N:". The float's own group ends the settings.
\newcommand{\figcaption}[1]{%
  \caption{\sffamily\fontsize{9.5}{12.5}\selectfont\RaggedRight
    #1\hspace{\linewidth}}}
% The notes refer to a figure from the sentence beside it, so these parameters
% make LaTeX try hard to set each float where it stands rather than collecting
% them at the top of a page. The float package's [H] would pin them
% absolutely, but it is not compatible with the tagging code, and confining
% them per section with placeins pushes the larger ones onto pages of their
% own. \FloatBarrier is available for a document that needs it locally.
%
% The cost of the "!": figures held over from one page can fill the top of
% the next, and a display or a kept block after them that is taller than the
% room left cannot be split, so it runs down towards the running foot.
% buildtex.py names such a page. \textfraction does nothing while the "!" is
% there, and dropping it with a larger \textfraction moved figures up to two
% pages from their text across the ChE 621 notes, so the page is mended
% locally: a shorter caption, a narrower figure, or the block moved.
\renewcommand{\fps@figure}{!ht}
\renewcommand{\fps@table}{!ht}
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.7}
\renewcommand{\textfraction}{0.06}
\renewcommand{\floatpagefraction}{0.75}
\setcounter{topnumber}{3}
\setcounter{bottomnumber}{2}
\setcounter{totalnumber}{5}

% ------------------------------------------------------------------- tables
% Tables are set without rules: \hline and the booktabs rules both abort the
% run under the tagging code, so the header row is marked by type and space.
\renewcommand{\arraystretch}{1.35}
\newcommand{\theadcell}[1]{{\sffamily\bfseries #1}}

% ------------------------------------------------------------------- lists
\setlist{topsep=4pt,itemsep=3pt,parsep=0pt,leftmargin=1.6em}

% --------------------------------------------------------------------- misc
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\raggedbottom
% Ragged right rather than justified: even word spacing is easier to track,
% and it avoids the rivers that justification opens up in a narrow measure.
% Ragged right rather than justified. The tagging code re-enters horizontal
% mode for every paragraph, which puts \rightskip back, so the setting has to
% be reapplied from the paragraph hook rather than once at the start.
\AddToHook{begindocument/end}{%
  \rightskip=0pt plus 2.2em\relax
  \spaceskip=\fontdimen2\font plus \fontdimen3\font minus \fontdimen4\font
  \parfillskip=0pt plus 1fil\relax
  \hbadness=10000 \hfuzz=2pt}

\hypersetup{colorlinks=true,linkcolor=nt@accent,urlcolor=nt@accent,
            pdfdisplaydoctitle=true}

\endinput
