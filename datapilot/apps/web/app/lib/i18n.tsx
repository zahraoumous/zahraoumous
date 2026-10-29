"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Locale = "en" | "fr" | "ar";
export type Theme = "light" | "dark" | "system";
type Params = Record<string, string | number>;
const messages: Record<string, {fr:string;ar:string}> = {
  "Language": {
    "fr": "Langue",
    "ar": "اللغة"
  },
  "Theme": {
    "fr": "Apparence",
    "ar": "المظهر"
  },
  "Light mode": {
    "fr": "Mode clair",
    "ar": "الوضع الفاتح"
  },
  "Dark mode": {
    "fr": "Mode sombre",
    "ar": "الوضع الداكن"
  },
  "System theme": {
    "fr": "Thème système",
    "ar": "مظهر النظام"
  },
  "Workspace": {
    "fr": "Espace de travail",
    "ar": "مساحة العمل"
  },
  "Overview": {
    "fr": "Vue d’ensemble",
    "ar": "نظرة عامة"
  },
  "Data sources": {
    "fr": "Sources de données",
    "ar": "مصادر البيانات"
  },
  "Import sources": {
    "fr": "Importer des sources",
    "ar": "استيراد المصادر"
  },
  "Executions": {
    "fr": "Exécutions",
    "ar": "عمليات التنفيذ"
  },
  "Data quality": {
    "fr": "Qualité des données",
    "ar": "جودة البيانات"
  },
  "Cleaning review": {
    "fr": "Révision du nettoyage",
    "ar": "مراجعة التنظيف"
  },
  "Analysis setup": {
    "fr": "Configuration de l’analyse",
    "ar": "إعداد التحليل"
  },
  "Analysis results": {
    "fr": "Résultats d’analyse",
    "ar": "نتائج التحليل"
  },
  "Insights": {
    "fr": "Enseignements",
    "ar": "الاستنتاجات"
  },
  "Dashboard": {
    "fr": "Tableau de bord",
    "ar": "لوحة المعلومات"
  },
  "Ask your data": {
    "fr": "Interroger les données",
    "ar": "اسأل بياناتك"
  },
  "Export & report": {
    "fr": "Exports et rapports",
    "ar": "التصدير والتقارير"
  },
  "AI settings": {
    "fr": "Paramètres IA",
    "ar": "إعدادات الذكاء الاصطناعي"
  },
  "Settings": {
    "fr": "Paramètres",
    "ar": "الإعدادات"
  },
  "Your data, in one place.": {
    "fr": "Vos données, au même endroit.",
    "ar": "بياناتك في مكان واحد."
  },
  "Bring your sources together.": {
    "fr": "Rassemblez vos sources.",
    "ar": "اجمع مصادرك."
  },
  "Every execution, accounted for.": {
    "fr": "Chaque exécution, suivie.",
    "ar": "تتبّع كل عملية تنفيذ."
  },
  "Dataset preview": {
    "fr": "Aperçu du jeu de données",
    "ar": "معاينة مجموعة البيانات"
  },
  "Loading your workspace": {
    "fr": "Chargement de votre espace",
    "ar": "جارٍ تحميل مساحة العمل"
  },
  "Loading sources": {
    "fr": "Chargement des sources",
    "ar": "جارٍ تحميل المصادر"
  },
  "Loading dataset": {
    "fr": "Chargement du jeu de données",
    "ar": "جارٍ تحميل مجموعة البيانات"
  },
  "No matching sources": {
    "fr": "Aucune source correspondante",
    "ar": "لا توجد مصادر مطابقة"
  },
  "Your first source belongs here": {
    "fr": "Votre première source vous attend ici",
    "ar": "ابدأ بإضافة مصدرك الأول"
  },
  "Clear search": {
    "fr": "Effacer la recherche",
    "ar": "مسح البحث"
  },
  "Try a different file name or folder path.": {
    "fr": "Essayez un autre nom de fichier ou chemin de dossier.",
    "ar": "جرّب اسم ملف أو مسار مجلد آخر."
  },
  "Import spreadsheets individually or choose a folder. Each file becomes a separate, traceable dataset.": {
    "fr": "Importez des feuilles de calcul ou choisissez un dossier. Chaque fichier devient un jeu de données distinct et traçable.",
    "ar": "استورد ملفات جداول أو اختر مجلداً. يصبح كل ملف مجموعة بيانات مستقلة قابلة للتتبّع."
  },
  "Source": {
    "fr": "Source",
    "ar": "المصدر"
  },
  "Status": {
    "fr": "Statut",
    "ar": "الحالة"
  },
  "Rows": {
    "fr": "Lignes",
    "ar": "الصفوف"
  },
  "Columns": {
    "fr": "Colonnes",
    "ar": "الأعمدة"
  },
  "Imported": {
    "fr": "Importé le",
    "ar": "تاريخ الاستيراد"
  },
  "Open": {
    "fr": "Ouvrir",
    "ar": "فتح"
  },
  "Source import": {
    "fr": "Import de sources",
    "ar": "استيراد المصادر"
  },
  "View data": {
    "fr": "Voir les données",
    "ar": "عرض البيانات"
  },
  "Successful files are kept. Retry processes failed files only.": {
    "fr": "Les fichiers réussis sont conservés. Seuls les fichiers en échec sont relancés.",
    "ar": "تُحفظ الملفات الناجحة. تُعاد معالجة الملفات الفاشلة فقط."
  },
  "Queuing…": {
    "fr": "Mise en file…",
    "ar": "جارٍ الإضافة إلى الطابور…"
  },
  "Retry failed files": {
    "fr": "Relancer les fichiers en échec",
    "ar": "إعادة محاولة الملفات الفاشلة"
  },
  "Workspace name": {
    "fr": "Nom de l’espace de travail",
    "ar": "اسم مساحة العمل"
  },
  "Keep a project’s sources and processing history together. You’ll be the workspace owner.": {
    "fr": "Regroupez les sources et l’historique du projet. Vous serez propriétaire de cet espace.",
    "ar": "اجمع مصادر المشروع وسجل معالجته. ستكون مالك مساحة العمل."
  },
  "Cancel": {
    "fr": "Annuler",
    "ar": "إلغاء"
  },
  "Creating workspace…": {
    "fr": "Création de l’espace…",
    "ar": "جارٍ إنشاء مساحة العمل…"
  },
  "Create workspace": {
    "fr": "Créer un espace de travail",
    "ar": "إنشاء مساحة عمل"
  },
  "A clearer home for your data.": {
    "fr": "Un espace plus clair pour vos données.",
    "ar": "مساحة أوضح لبياناتك."
  },
  "Create an account to organize your files, run imports, and see the results in your own workspace.": {
    "fr": "Créez un compte pour organiser vos fichiers, lancer des imports et consulter les résultats dans votre espace.",
    "ar": "أنشئ حساباً لتنظيم ملفاتك وتشغيل الاستيراد وعرض النتائج في مساحة عملك."
  },
  "Sign in or create an account": {
    "fr": "Se connecter ou créer un compte",
    "ar": "تسجيل الدخول أو إنشاء حساب"
  },
  "Real accounts, persistent workspaces, and visible executions.": {
    "fr": "Des comptes réels, des espaces persistants et des exécutions visibles.",
    "ar": "حسابات محلية ومساحات عمل محفوظة وعمليات تنفيذ مرئية."
  },
  "Start with a workspace.": {
    "fr": "Commencez par un espace de travail.",
    "ar": "ابدأ بمساحة عمل."
  },
  "A place for your source files, their quality checks, and the work you do next. Give it a name that makes sense for your project.": {
    "fr": "Un espace pour vos fichiers, leurs contrôles qualité et vos prochaines analyses. Choisissez un nom adapté à votre projet.",
    "ar": "مساحة لملفاتك وفحوص جودتها وأعمالك القادمة. اختر اسماً مناسباً لمشروعك."
  },
  "Account created": {
    "fr": "Compte créé",
    "ar": "تم إنشاء الحساب"
  },
  "Explore results": {
    "fr": "Explorer les résultats",
    "ar": "استكشاف النتائج"
  },
  "See executions": {
    "fr": "Voir les exécutions",
    "ar": "عرض عمليات التنفيذ"
  },
  "Files in this workspace": {
    "fr": "Fichiers dans cet espace",
    "ar": "ملفات مساحة العمل"
  },
  "Rows processed": {
    "fr": "Lignes traitées",
    "ar": "الصفوف المعالَجة"
  },
  "Across ready datasets": {
    "fr": "Dans les jeux de données prêts",
    "ar": "في مجموعات البيانات الجاهزة"
  },
  "In progress": {
    "fr": "En cours",
    "ar": "قيد التنفيذ"
  },
  "Queued and running files": {
    "fr": "Fichiers en attente et en cours",
    "ar": "الملفات المنتظرة والجارية"
  },
  "Need attention": {
    "fr": "À examiner",
    "ar": "تحتاج إلى مراجعة"
  },
  "Failed files to review": {
    "fr": "Fichiers en échec à examiner",
    "ar": "ملفات فاشلة للمراجعة"
  },
  "Recent sources": {
    "fr": "Sources récentes",
    "ar": "المصادر الحديثة"
  },
  "Your original files stay preserved.": {
    "fr": "Vos fichiers originaux sont conservés.",
    "ar": "تُحفظ ملفاتك الأصلية."
  },
  "All sources": {
    "fr": "Toutes les sources",
    "ar": "جميع المصادر"
  },
  "Latest execution": {
    "fr": "Dernière exécution",
    "ar": "أحدث عملية تنفيذ"
  },
  "Execution history": {
    "fr": "Historique des exécutions",
    "ar": "سجل التنفيذ"
  },
  "Files or a folder. Your choice.": {
    "fr": "Des fichiers ou un dossier. À vous de choisir.",
    "ar": "ملفات أو مجلد. الخيار لك."
  },
  "Drop CSV or XLSX files here, or browse your computer.": {
    "fr": "Déposez vos fichiers CSV ou XLSX ici, ou parcourez votre ordinateur.",
    "ar": "أفلت ملفات CSV أو XLSX هنا أو تصفّح جهازك."
  },
  "Choose files": {
    "fr": "Choisir des fichiers",
    "ar": "اختيار ملفات"
  },
  "Choose folder": {
    "fr": "Choisir un dossier",
    "ar": "اختيار مجلد"
  },
  "Folder selection includes supported files in subfolders.": {
    "fr": "Les fichiers compatibles des sous-dossiers sont inclus.",
    "ar": "يتضمن اختيار المجلد الملفات المدعومة في المجلدات الفرعية."
  },
  "Your viewer role can inspect sources but cannot import files.": {
    "fr": "Votre rôle lecteur permet de consulter les sources, mais pas d’importer des fichiers.",
    "ar": "يمكن لدور المشاهد فحص المصادر دون استيراد الملفات."
  },
  "Import manifest": {
    "fr": "Liste d’import",
    "ar": "قائمة الاستيراد"
  },
  "Relative paths are kept. Each file becomes one dataset.": {
    "fr": "Les chemins relatifs sont conservés. Chaque fichier devient un jeu de données.",
    "ar": "تُحفظ المسارات النسبية. يصبح كل ملف مجموعة بيانات."
  },
  "Clear selection": {
    "fr": "Effacer la sélection",
    "ar": "مسح التحديد"
  },
  "No files selected yet. Choose files or a folder to build your import.": {
    "fr": "Aucun fichier sélectionné. Choisissez des fichiers ou un dossier.",
    "ar": "لم تُحدَّد ملفات بعد. اختر ملفات أو مجلداً للاستيراد."
  },
  "Latest import": {
    "fr": "Dernier import",
    "ar": "أحدث استيراد"
  },
  "Updates automatically": {
    "fr": "Mise à jour automatique",
    "ar": "يُحدَّث تلقائياً"
  },
  "Import summary": {
    "fr": "Résumé de l’import",
    "ar": "ملخص الاستيراد"
  },
  "Destination": {
    "fr": "Destination",
    "ar": "الوجهة"
  },
  "Selected files": {
    "fr": "Fichiers sélectionnés",
    "ar": "الملفات المحددة"
  },
  "Total size": {
    "fr": "Taille totale",
    "ar": "الحجم الإجمالي"
  },
  "Import name": {
    "fr": "Nom de l’import",
    "ar": "اسم الاستيراد"
  },
  "optional": {
    "fr": "facultatif",
    "ar": "اختياري"
  },
  "Uploading sources": {
    "fr": "Envoi des sources",
    "ar": "جارٍ رفع المصادر"
  },
  "Preparing your import": {
    "fr": "Préparation de l’import",
    "ar": "جارٍ تجهيز الاستيراد"
  },
  "Keep this tab open until the import is received.": {
    "fr": "Gardez cet onglet ouvert jusqu’à réception de l’import.",
    "ar": "أبقِ علامة التبويب مفتوحة حتى استلام الملفات."
  },
  "Importing…": {
    "fr": "Import en cours…",
    "ar": "جارٍ الاستيراد…"
  },
  "Know what happens next": {
    "fr": "La suite des opérations",
    "ar": "ما الذي يحدث بعد ذلك"
  },
  "We preserve your original files, process them separately, and report progress and quality findings for each source.": {
    "fr": "Nous conservons les originaux, traitons les fichiers séparément et présentons leur progression et leurs résultats qualité.",
    "ar": "نحفظ الملفات الأصلية ونعالجها بشكل مستقل ونعرض التقدم ونتائج الجودة لكل مصدر."
  },
  "CSV and XLSX formats": {
    "fr": "Formats CSV et XLSX",
    "ar": "صيغتا CSV وXLSX"
  },
  "Up to 25 MiB per file": {
    "fr": "Jusqu’à 25 Mio par fichier",
    "ar": "حتى 25 ميبيبايت لكل ملف"
  },
  "Up to 100 MiB per import": {
    "fr": "Jusqu’à 100 Mio par import",
    "ar": "حتى 100 ميبيبايت لكل استيراد"
  },
  "Up to 250,000 rows and 50 columns per file": {
    "fr": "Jusqu’à 250 000 lignes et 50 colonnes par fichier",
    "ar": "حتى 250,000 صف و50 عموداً لكل ملف"
  },
  "XLSX imports use the first visible worksheet": {
    "fr": "Les imports XLSX utilisent la première feuille visible",
    "ar": "يستخدم استيراد XLSX أول ورقة عمل مرئية"
  },
  "Folder selection uses your browser’s folder picker. If unavailable, select multiple files instead.": {
    "fr": "La sélection de dossier dépend du navigateur. Si elle est indisponible, sélectionnez plusieurs fichiers.",
    "ar": "يعتمد اختيار المجلد على متصفحك. يمكنك تحديد عدة ملفات إذا لم يكن متاحاً."
  },
  "Your execution history starts here": {
    "fr": "Votre historique commence ici",
    "ar": "يبدأ سجل التنفيذ هنا"
  },
  "Import a file or folder to run your first processing job. Every file’s status and outcome will appear here.": {
    "fr": "Importez un fichier ou un dossier pour lancer le premier traitement. L’état et le résultat de chaque fichier apparaîtront ici.",
    "ar": "استورد ملفاً أو مجلداً لتشغيل أول معالجة. ستظهر هنا حالة كل ملف ونتيجته."
  },
  "Workspace sources": {
    "fr": "Sources de l’espace",
    "ar": "مصادر مساحة العمل"
  },
  "Search files by name or folder path.": {
    "fr": "Recherchez par nom de fichier ou chemin de dossier.",
    "ar": "ابحث باسم الملف أو مسار المجلد."
  },
  "Find a source…": {
    "fr": "Rechercher une source…",
    "ar": "البحث عن مصدر…"
  },
  "Find a source": {
    "fr": "Rechercher une source",
    "ar": "البحث عن مصدر"
  },
  "Choose a source to explore": {
    "fr": "Choisissez une source à explorer",
    "ar": "اختر مصدراً لاستكشافه"
  },
  "Import your first file, then open its preview and quality results from the data sources list.": {
    "fr": "Importez un fichier, puis ouvrez son aperçu et ses résultats qualité depuis la liste des sources.",
    "ar": "استورد ملفك الأول ثم افتح معاينته ونتائج جودته من قائمة المصادر."
  },
  "This source needs attention": {
    "fr": "Cette source nécessite une intervention",
    "ar": "هذا المصدر يحتاج إلى مراجعة"
  },
  "Your source is being processed": {
    "fr": "Votre source est en cours de traitement",
    "ar": "جارٍ معالجة المصدر"
  },
  "View execution details": {
    "fr": "Voir les détails d’exécution",
    "ar": "عرض تفاصيل التنفيذ"
  },
  "See per-file progress or the failure reason in executions. Results appear once processing completes.": {
    "fr": "Consultez la progression ou les erreurs dans les exécutions. Les résultats apparaissent après le traitement.",
    "ar": "اطّلع على تقدم الملفات أو أسباب الفشل في عمليات التنفيذ. تظهر النتائج بعد اكتمال المعالجة."
  },
  "No findings from the implemented checks": {
    "fr": "Aucun problème détecté par les contrôles disponibles",
    "ar": "لم تكتشف الفحوص المتاحة مشكلات"
  },
  "Quality findings": {
    "fr": "Résultats qualité",
    "ar": "نتائج الجودة"
  },
  "Review each finding in the context of your data.": {
    "fr": "Examinez chaque résultat dans le contexte de vos données.",
    "ar": "راجع كل نتيجة في سياق بياناتك."
  },
  "Check": {
    "fr": "Contrôle",
    "ar": "الفحص"
  },
  "Severity": {
    "fr": "Gravité",
    "ar": "الخطورة"
  },
  "Column": {
    "fr": "Colonne",
    "ar": "العمود"
  },
  "Affected rows": {
    "fr": "Lignes concernées",
    "ar": "الصفوف المتأثرة"
  },
  "Details": {
    "fr": "Détails",
    "ar": "التفاصيل"
  },
  "All columns": {
    "fr": "Toutes les colonnes",
    "ar": "جميع الأعمدة"
  },
  "No quality findings were reported. You can inspect the source preview and inferred schema.": {
    "fr": "Aucun problème de qualité signalé. Consultez l’aperçu et le schéma déduit.",
    "ar": "لم تُسجَّل مشكلات جودة. يمكنك فحص معاينة المصدر والمخطط المستنتج."
  },
  "Missing cells": {
    "fr": "Cellules manquantes",
    "ar": "الخلايا المفقودة"
  },
  "Dataset view": {
    "fr": "Vue du jeu de données",
    "ar": "عرض مجموعة البيانات"
  },
  "Data preview": {
    "fr": "Aperçu des données",
    "ar": "معاينة البيانات"
  },
  "Column schema": {
    "fr": "Schéma des colonnes",
    "ar": "مخطط الأعمدة"
  },
  "Quality report": {
    "fr": "Rapport qualité",
    "ar": "تقرير الجودة"
  },
  "Original source preserved": {
    "fr": "Source originale conservée",
    "ar": "المصدر الأصلي محفوظ"
  },
  "Missing value": {
    "fr": "Valeur manquante",
    "ar": "قيمة مفقودة"
  },
  "empty": {
    "fr": "vide",
    "ar": "فارغ"
  },
  "This source has no data rows.": {
    "fr": "Cette source ne contient aucune ligne de données.",
    "ar": "لا يحتوي هذا المصدر على صفوف بيانات."
  },
  "Inferred type": {
    "fr": "Type déduit",
    "ar": "النوع المستنتج"
  },
  "Missing values": {
    "fr": "Valeurs manquantes",
    "ar": "القيم المفقودة"
  },
  "Completeness": {
    "fr": "Complétude",
    "ar": "الاكتمال"
  },
  "Source provenance": {
    "fr": "Provenance de la source",
    "ar": "مصدر البيانات"
  },
  "Dataset version": {
    "fr": "Version du jeu de données",
    "ar": "إصدار مجموعة البيانات"
  },
  "Source SHA-256": {
    "fr": "SHA-256 de la source",
    "ar": "بصمة SHA-256 للمصدر"
  },
  "No workspace yet": {
    "fr": "Aucun espace pour le moment",
    "ar": "لا توجد مساحة عمل بعد"
  },
  "New workspace": {
    "fr": "Nouvel espace",
    "ar": "مساحة عمل جديدة"
  },
  "Your originals stay intact.": {
    "fr": "Vos originaux restent intacts.",
    "ar": "تبقى ملفاتك الأصلية محفوظة."
  },
  "Every source, traceable.": {
    "fr": "Chaque source est traçable.",
    "ar": "كل مصدر قابل للتتبّع."
  },
  "Your account": {
    "fr": "Votre compte",
    "ar": "حسابك"
  },
  "Sign out": {
    "fr": "Se déconnecter",
    "ar": "تسجيل الخروج"
  },
  "Sign in": {
    "fr": "Se connecter",
    "ar": "تسجيل الدخول"
  },
  "Your workspace": {
    "fr": "Votre espace de travail",
    "ar": "مساحة عملك"
  },
  "Dataset": {
    "fr": "Jeu de données",
    "ar": "مجموعة البيانات"
  },
  "Connected": {
    "fr": "Connecté",
    "ar": "متصل"
  },
  "Local edition": {
    "fr": "Édition locale",
    "ar": "الإصدار المحلي"
  },
  "Refresh workspace": {
    "fr": "Actualiser l’espace",
    "ar": "تحديث مساحة العمل"
  },
  "Dismiss error": {
    "fr": "Fermer l’erreur",
    "ar": "إغلاق الخطأ"
  },
  "Dismiss notice": {
    "fr": "Fermer le message",
    "ar": "إغلاق الإشعار"
  },
  "Source files preserved. Results grounded in your data.": {
    "fr": "Fichiers sources conservés. Résultats fondés sur vos données.",
    "ar": "الملفات الأصلية محفوظة. النتائج مبنية على بياناتك."
  },
  "Close workspace dialog": {
    "fr": "Fermer la fenêtre de création",
    "ar": "إغلاق نافذة مساحة العمل"
  },
  "A new workspace.": {
    "fr": "Un nouvel espace.",
    "ar": "مساحة عمل جديدة."
  },
  "Give your next project a place of its own.": {
    "fr": "Offrez un espace dédié à votre prochain projet.",
    "ar": "خصّص مساحة لمشروعك القادم."
  },
  "Select multiple data files or a whole folder. Follow each one from upload to results.": {
    "fr": "Sélectionnez plusieurs fichiers ou un dossier. Suivez chacun de l’envoi aux résultats.",
    "ar": "اختر عدة ملفات أو مجلداً كاملاً. تتبّع كل ملف من الرفع حتى النتائج."
  },
  "Processing status, per-file outcomes, and a clear path to retry.": {
    "fr": "Statut des traitements, résultats par fichier et relance des échecs.",
    "ar": "حالة المعالجة ونتائج كل ملف وخيار إعادة المحاولة."
  },
  "Organize your sources. See the work happening. Explore the results.": {
    "fr": "Organisez vos sources, suivez les traitements et explorez les résultats.",
    "ar": "نظّم مصادرك وتابع المعالجة واستكشف النتائج."
  },
  "Checks from the actual imported dataset, ready for your review.": {
    "fr": "Des contrôles sur les données réellement importées, prêts à examiner.",
    "ar": "فحوص على البيانات المستوردة الفعلية، جاهزة للمراجعة."
  },
  "Every imported file, with its processing status and original path.": {
    "fr": "Chaque fichier importé, son statut de traitement et son chemin d’origine.",
    "ar": "كل ملف مستورد مع حالة معالجته ومساره الأصلي."
  },
  "A closer look at your imported file and its inferred structure.": {
    "fr": "Examinez votre fichier importé et sa structure déduite.",
    "ar": "نظرة تفصيلية على الملف المستورد وبنيته المستنتجة."
  },
  "Workspace navigation": {
    "fr": "Navigation de l’espace",
    "ar": "التنقل في مساحة العمل"
  },
  "Select multiple CSV or XLSX files": {
    "fr": "Sélectionner plusieurs fichiers CSV ou XLSX",
    "ar": "تحديد عدة ملفات CSV أو XLSX"
  },
  "Select a datasource folder": {
    "fr": "Sélectionner un dossier de sources",
    "ar": "تحديد مجلد مصادر البيانات"
  },
  "e.g. Operations, Sales, Research": {
    "fr": "Ex. : Opérations, Ventes, Recherche",
    "ar": "مثال: العمليات، المبيعات، البحث"
  },
  " e.g. Monthly operations": {
    "fr": "Ex. : Opérations mensuelles",
    "ar": "مثال: العمليات الشهرية"
  },
  "Workspace created. You can now import your sources.": {
    "fr": "Espace créé. Vous pouvez importer vos sources.",
    "ar": "تم إنشاء مساحة العمل. يمكنك الآن استيراد مصادرك."
  },
  "Files received. Processing is queued; results will appear as each file completes.": {
    "fr": "Fichiers reçus. Le traitement est en attente ; les résultats apparaîtront à mesure.",
    "ar": "تم استلام الملفات ووضعها في طابور المعالجة. ستظهر النتائج عند اكتمال كل ملف."
  },
  "Failed files queued for another attempt.": {
    "fr": "Les fichiers en échec ont été remis en attente.",
    "ar": "أُضيفت الملفات الفاشلة إلى الطابور للمحاولة مجدداً."
  },
  "Select at most 100 files per import.": {
    "fr": "Sélectionnez au maximum 100 fichiers par import.",
    "ar": "حدّد 100 ملف كحد أقصى لكل استيراد."
  },
  "The selected files exceed the 100 MiB batch limit. Remove files or split this import.": {
    "fr": "La sélection dépasse 100 Mio. Retirez des fichiers ou divisez cet import.",
    "ar": "تتجاوز الملفات المحددة 100 ميبيبايت. أزل بعض الملفات أو قسّم الاستيراد."
  },
  "Wait for the upload to finish before leaving this page. Processing will continue in the background after your files are received.": {
    "fr": "Attendez la fin de l’envoi avant de quitter cette page. Le traitement continuera en arrière-plan après réception.",
    "ar": "انتظر اكتمال الرفع قبل مغادرة الصفحة. تستمر المعالجة في الخلفية بعد استلام الملفات."
  },
  "The server returned an unreadable response.": {
    "fr": "Le serveur a renvoyé une réponse illisible.",
    "ar": "أعاد الخادم استجابة غير مقروءة."
  },
  "The upload could not reach the server. Check your connection and try again.": {
    "fr": "L’envoi n’a pas atteint le serveur. Vérifiez votre connexion et réessayez.",
    "ar": "تعذّر وصول الرفع إلى الخادم. تحقّق من اتصالك وحاول مجدداً."
  },
  "The upload timed out. Check executions before retrying.": {
    "fr": "L’envoi a expiré. Vérifiez les exécutions avant de réessayer.",
    "ar": "انتهت مهلة الرفع. راجع عمليات التنفيذ قبل إعادة المحاولة."
  },
  "Upload interrupted. Check executions before retrying.": {
    "fr": "Envoi interrompu. Vérifiez les exécutions avant de réessayer.",
    "ar": "انقطع الرفع. راجع عمليات التنفيذ قبل إعادة المحاولة."
  },
  "only CSV and XLSX files are supported.": {
    "fr": "seuls les fichiers CSV et XLSX sont acceptés.",
    "ar": "ملفات CSV وXLSX فقط مدعومة."
  },
  "empty files cannot be imported.": {
    "fr": "les fichiers vides ne peuvent pas être importés.",
    "ar": "لا يمكن استيراد ملفات فارغة."
  },
  "exceeds the 25 MiB file limit.": {
    "fr": "dépasse la limite de 25 Mio par fichier.",
    "ar": "يتجاوز حد 25 ميبيبايت للملف."
  },
  "this path is already selected.": {
    "fr": "ce chemin est déjà sélectionné.",
    "ar": "هذا المسار محدد بالفعل."
  },
  "A focused workspace for turning scattered spreadsheets into clear, dependable data.": {
    "fr": "Un espace dédié pour transformer des feuilles éparpillées en données claires et fiables.",
    "ar": "مساحة عمل لتحويل الجداول المتفرقة إلى بيانات واضحة وموثوقة."
  },
  "Multiple files. One workspace.": {
    "fr": "Plusieurs fichiers. Un seul espace.",
    "ar": "ملفات متعددة. مساحة عمل واحدة."
  },
  "Quality checks with actual evidence.": {
    "fr": "Contrôles qualité étayés par les données.",
    "ar": "فحوص جودة مدعومة بالأدلة."
  },
  "Real jobs. Visible progress.": {
    "fr": "Des traitements réels. Une progression visible.",
    "ar": "معالجة فعلية. تقدم مرئي."
  },
  "Built for a clearer way to work.": {
    "fr": "Conçu pour travailler plus clairement.",
    "ar": "مصمم لعمل أكثر وضوحاً."
  },
  "Welcome to DataPilot": {
    "fr": "Bienvenue sur DataPilot",
    "ar": "مرحباً بك في DataPilot"
  },
  "Create your account.": {
    "fr": "Créez votre compte.",
    "ar": "أنشئ حسابك."
  },
  "Sign in to your workspace.": {
    "fr": "Connectez-vous à votre espace.",
    "ar": "سجّل الدخول إلى مساحة عملك."
  },
  "Create your account, then bring your first data sources together.": {
    "fr": "Créez votre compte, puis rassemblez vos premières sources.",
    "ar": "أنشئ حسابك ثم اجمع مصادر بياناتك الأولى."
  },
  "Sign in to your workspaces, sources, and executions.": {
    "fr": "Connectez-vous à vos espaces, sources et exécutions.",
    "ar": "سجّل الدخول إلى مساحات عملك ومصادرك وعمليات التنفيذ."
  },
  "Account action": {
    "fr": "Action du compte",
    "ar": "إجراء الحساب"
  },
  "Create account": {
    "fr": "Créer un compte",
    "ar": "إنشاء حساب"
  },
  "Your name": {
    "fr": "Votre nom",
    "ar": "اسمك"
  },
  "Email address": {
    "fr": "Adresse e-mail",
    "ar": "البريد الإلكتروني"
  },
  "Password": {
    "fr": "Mot de passe",
    "ar": "كلمة المرور"
  },
  "At least 12 characters": {
    "fr": "Au moins 12 caractères",
    "ar": "12 حرفاً على الأقل"
  },
  "Enter your password": {
    "fr": "Saisissez votre mot de passe",
    "ar": "أدخل كلمة المرور"
  },
  "Use at least 12 characters. There are no default accounts.": {
    "fr": "Utilisez au moins 12 caractères. Aucun compte par défaut n’existe.",
    "ar": "استخدم 12 حرفاً على الأقل. لا توجد حسابات افتراضية."
  },
  "Creating your account…": {
    "fr": "Création du compte…",
    "ar": "جارٍ إنشاء حسابك…"
  },
  "Signing you in…": {
    "fr": "Connexion…",
    "ar": "جارٍ تسجيل الدخول…"
  },
  "Your workspaces are private to your account.": {
    "fr": "Vos espaces sont privés à votre compte.",
    "ar": "مساحات عملك خاصة بحسابك."
  },
  "Bring data together. Move forward with confidence.": {
    "fr": "Rassemblez vos données. Avancez en confiance.",
    "ar": "اجمع البيانات وتقدّم بثقة."
  },
  "Something went wrong. Please try again.": {
    "fr": "Une erreur s’est produite. Réessayez.",
    "ar": "حدث خطأ. يرجى المحاولة مجدداً."
  },
  "The request could not be completed. Please try again.": {
    "fr": "La requête n’a pas abouti. Réessayez.",
    "ar": "تعذّر إكمال الطلب. يرجى المحاولة مجدداً."
  },
  "Invalid input": {
    "fr": "Saisie invalide",
    "ar": "إدخال غير صالح"
  },
  "Email or password is incorrect": {
    "fr": "Adresse e-mail ou mot de passe incorrect",
    "ar": "البريد الإلكتروني أو كلمة المرور غير صحيحة"
  },
  "This email is already registered": {
    "fr": "Cette adresse e-mail est déjà enregistrée",
    "ar": "هذا البريد الإلكتروني مسجل بالفعل"
  },
  "Sign in to continue": {
    "fr": "Connectez-vous pour continuer",
    "ar": "سجّل الدخول للمتابعة"
  },
  "Workspace not found": {
    "fr": "Espace introuvable",
    "ar": "مساحة العمل غير موجودة"
  },
  "Dataset not found": {
    "fr": "Jeu de données introuvable",
    "ar": "مجموعة البيانات غير موجودة"
  },
  "ready": {
    "fr": "prêt",
    "ar": "جاهز"
  },
  "completed": {
    "fr": "terminé",
    "ar": "مكتمل"
  },
  "running": {
    "fr": "en cours",
    "ar": "جارٍ"
  },
  "queued": {
    "fr": "en attente",
    "ar": "في الطابور"
  },
  "uploaded": {
    "fr": "envoyé",
    "ar": "مرفوع"
  },
  "failed": {
    "fr": "échec",
    "ar": "فاشل"
  },
  "partial": {
    "fr": "partiel",
    "ar": "جزئي"
  },
  "cancelled": {
    "fr": "annulé",
    "ar": "ملغى"
  },
  "warning": {
    "fr": "avertissement",
    "ar": "تحذير"
  },
  "critical": {
    "fr": "critique",
    "ar": "حرج"
  },
  "info": {
    "fr": "information",
    "ar": "معلومة"
  },
  "owner": {
    "fr": "propriétaire",
    "ar": "مالك"
  },
  "analyst": {
    "fr": "analyste",
    "ar": "محلل"
  },
  "viewer": {
    "fr": "lecteur",
    "ar": "مشاهد"
  },
  "Duplicate rows": {
    "fr": "Lignes dupliquées",
    "ar": "الصفوف المكررة"
  },
  "Mixed types": {
    "fr": "Types mixtes",
    "ar": "أنواع مختلطة"
  },
  "Formula like text": {
    "fr": "Texte ressemblant à une formule",
    "ar": "نص يشبه الصيغ"
  },
  "{count} of {total} completed": {
    "fr": "{count} sur {total} terminés",
    "ar": "اكتمل {count} من {total}"
  },
  "{count} of {total} files completed": {
    "fr": "{count} fichiers sur {total} terminés",
    "ar": "اكتمل {count} ملف من {total}"
  },
  "{count} findings to review": {
    "fr": "{count} résultats à examiner",
    "ar": "{count} نتائج للمراجعة"
  },
  "Based on {rows} rows and {columns} columns. Findings flag possible issues; original data stays unchanged.": {
    "fr": "Sur {rows} lignes et {columns} colonnes. Les résultats signalent des problèmes possibles ; les données d’origine sont conservées.",
    "ar": "بناءً على {rows} صف و{columns} عمود. تشير النتائج إلى مشكلات محتملة وتبقى البيانات الأصلية محفوظة."
  },
  "Showing {count} of {total} rows": {
    "fr": "Affichage de {count} lignes sur {total}",
    "ar": "عرض {count} من {total} صف"
  },
  "Welcome to {name}.": {
    "fr": "Bienvenue dans {name}.",
    "ar": "مرحباً بك في {name}."
  },
  "{count} processing": {
    "fr": "{count} en cours",
    "ar": "{count} قيد المعالجة"
  },
  "{count} ready to explore": {
    "fr": "{count} prêts à explorer",
    "ar": "{count} جاهزة للاستكشاف"
  },
  "Import {count} file": {
    "fr": "Importer {count} fichier",
    "ar": "استيراد ملف واحد ({count})"
  },
  "Import {count} files": {
    "fr": "Importer {count} fichiers",
    "ar": "استيراد {count} ملفات"
  },
  "{count} file was not added": {
    "fr": "{count} fichier n’a pas été ajouté",
    "ar": "لم يُضف ملف واحد ({count})"
  },
  "{count} files were not added": {
    "fr": "{count} fichiers n’ont pas été ajoutés",
    "ar": "لم تُضف {count} ملفات"
  },
  "And {count} more unsupported files.": {
    "fr": "Et {count} autres fichiers non pris en charge.",
    "ar": "و{count} ملفات أخرى غير مدعومة."
  },
  "{count} files in progress": {
    "fr": "{count} fichiers en cours",
    "ar": "{count} ملفات قيد التنفيذ"
  },
  "{count} completed": {
    "fr": "{count} terminés",
    "ar": "{count} مكتملة"
  },
  "{count} failed": {
    "fr": "{count} en échec",
    "ar": "{count} فاشلة"
  },
  "Remove {path}": {
    "fr": "Retirer {path}",
    "ar": "إزالة {path}"
  },
  "Open {name}": {
    "fr": "Ouvrir {name}",
    "ar": "فتح {name}"
  },
  "{filename} processing": {
    "fr": "Traitement de {filename}",
    "ar": "جارٍ معالجة {filename}"
  },
  "Upload progress": {
    "fr": "Progression de l’envoi",
    "ar": "تقدم الرفع"
  },
  "Workbench": {
    "fr": "Atelier",
    "ar": "ورشة العمل"
  },
  "Review changes, calculate metrics, and explore evidence from your sources.": {
    "fr": "Révisez les changements, calculez les indicateurs et explorez les résultats de vos sources.",
    "ar": "راجع التغييرات واحسب المقاييس واستكشف الأدلة من مصادرك."
  },
  "From scattered files to a shared starting point.": {
    "fr": "Des fichiers épars à un point de départ commun.",
    "ar": "من ملفات متفرقة إلى نقطة انطلاق واحدة."
  },
  "Your sources and executions, with the latest processing results.": {
    "fr": "Vos sources et exécutions, avec les derniers résultats de traitement.",
    "ar": "مصادرك وعمليات التنفيذ مع أحدث نتائج المعالجة."
  },
  "Choose a folder or select multiple spreadsheets. We’ll keep their paths, process each file, and show you what’s inside.": {
    "fr": "Choisissez un dossier ou plusieurs feuilles de calcul. Nous conservons leurs chemins, traitons chaque fichier et présentons leur contenu.",
    "ar": "اختر مجلداً أو عدة جداول. نحفظ مساراتها ونعالج كل ملف ونعرض محتواه."
  },
  "Your spreadsheets": {
    "fr": "Vos feuilles de calcul",
    "ar": "جداول بياناتك"
  },
  "e.g. Monthly operations": {
    "fr": "Ex. : Opérations mensuelles",
    "ar": "مثال: العمليات الشهرية"
  },
  "A key is saved: {hint}": {
    "fr": "Une clé est enregistrée : {hint}",
    "ar": "يوجد مفتاح محفوظ: {hint}"
  },
  "AI settings saved.": {
    "fr": "Paramètres IA enregistrés.",
    "ar": "تم حفظ إعدادات الذكاء الاصطناعي."
  },
  "AI skill": {
    "fr": "Compétence IA",
    "ar": "مهارة الذكاء الاصطناعي"
  },
  "API key": {
    "fr": "Clé API",
    "ar": "مفتاح API"
  },
  "Add operation": {
    "fr": "Ajouter une opération",
    "ar": "إضافة عملية"
  },
  "Analysis name": {
    "fr": "Nom de l’analyse",
    "ar": "اسم التحليل"
  },
  "Analysis report": {
    "fr": "Rapport d’analyse",
    "ar": "تقرير التحليل"
  },
  "Analysis saved from the selected dataset version.": {
    "fr": "Analyse enregistrée à partir de la version sélectionnée.",
    "ar": "تم حفظ التحليل من إصدار مجموعة البيانات المحدد."
  },
  "Analyzing evidence…": {
    "fr": "Analyse des éléments…",
    "ar": "جارٍ تحليل الأدلة…"
  },
  "Answer and evidence": {
    "fr": "Réponse et éléments justificatifs",
    "ar": "الإجابة والأدلة"
  },
  "Ask with selected skill": {
    "fr": "Interroger avec la compétence choisie",
    "ar": "السؤال باستخدام المهارة المحددة"
  },
  "Build a cleaning plan": {
    "fr": "Élaborer un plan de nettoyage",
    "ar": "إنشاء خطة تنظيف"
  },
  "Calculating…": {
    "fr": "Calcul en cours…",
    "ar": "جارٍ الحساب…"
  },
  "Calculation evidence and mappings": {
    "fr": "Justificatifs des calculs et correspondances",
    "ar": "أدلة الحساب وربط الأعمدة"
  },
  "Categories, separated by commas": {
    "fr": "Catégories séparées par des virgules",
    "ar": "الفئات، مفصولة بفواصل"
  },
  "Changed cells": {
    "fr": "Cellules modifiées",
    "ar": "الخلايا المعدّلة"
  },
  "Changes apply to the full dataset, not only the displayed preview.": {
    "fr": "Les changements concernent toutes les données, pas seulement l’aperçu.",
    "ar": "تُطبَّق التغييرات على مجموعة البيانات كاملةً، وليس المعاينة فقط."
  },
  "Changing provider removes the previous provider key. Enter a new key for the selected provider.": {
    "fr": "Changer de fournisseur supprime la clé précédente. Saisissez une nouvelle clé.",
    "ar": "يؤدي تغيير المزوّد إلى حذف مفتاح المزوّد السابق. أدخل مفتاحاً جديداً للمزوّد المحدد."
  },
  "Choose a skill to guide an answer grounded in your dataset evidence.": {
    "fr": "Choisissez une compétence pour guider une réponse fondée sur vos données.",
    "ar": "اختر مهارة لتوجيه إجابة مبنية على أدلة مجموعة بياناتك."
  },
  "Cleaned": {
    "fr": "Nettoyé",
    "ar": "منظَّف"
  },
  "Cleaned version saved. Your original source is preserved.": {
    "fr": "Version nettoyée enregistrée. La source originale est conservée.",
    "ar": "تم حفظ الإصدار المنظَّف. المصدر الأصلي محفوظ."
  },
  "Cleaning operation": {
    "fr": "Opération de nettoyage",
    "ar": "عملية التنظيف"
  },
  "Confirm the meaning of your columns": {
    "fr": "Confirmez le sens de vos colonnes",
    "ar": "أكّد معنى أعمدتك"
  },
  "Confirm your column mapping and run an analysis to create metrics, insights, and a dashboard.": {
    "fr": "Confirmez les correspondances de colonnes et lancez une analyse pour créer indicateurs, enseignements et tableau de bord.",
    "ar": "أكّد ربط الأعمدة وشغّل تحليلاً لإنشاء المقاييس والاستنتاجات ولوحة المعلومات."
  },
  "Create a persistent dashboard from the selected analysis snapshot.": {
    "fr": "Créez un tableau de bord persistant à partir de cette analyse.",
    "ar": "أنشئ لوحة معلومات محفوظة من لقطة التحليل المحددة."
  },
  "Dashboard saved.": {
    "fr": "Tableau de bord enregistré.",
    "ar": "تم حفظ لوحة المعلومات."
  },
  "Dashboard title": {
    "fr": "Titre du tableau de bord",
    "ar": "عنوان لوحة المعلومات"
  },
  "Download the full selected dataset version. Spreadsheet exports neutralize formula-like text.": {
    "fr": "Téléchargez la version complète sélectionnée. Les exports neutralisent les textes ressemblant à des formules.",
    "ar": "نزّل إصدار البيانات المحدد كاملاً. يُحيَّد النص المشابه للصيغ في صادرات الجداول."
  },
  "Enter your provider API key": {
    "fr": "Saisissez votre clé API du fournisseur",
    "ar": "أدخل مفتاح API للمزوّد"
  },
  "Evidence": {
    "fr": "Éléments justificatifs",
    "ar": "الأدلة"
  },
  "Evidence and insights": {
    "fr": "Éléments et enseignements",
    "ar": "الأدلة والاستنتاجات"
  },
  "Export dataset": {
    "fr": "Exporter les données",
    "ar": "تصدير مجموعة البيانات"
  },
  "Export downloaded.": {
    "fr": "Export téléchargé.",
    "ar": "تم تنزيل التصدير."
  },
  "Export the selected saved analysis with its metrics, evidence, and provenance.": {
    "fr": "Exportez l’analyse enregistrée avec ses indicateurs, justificatifs et provenance.",
    "ar": "صدّر التحليل المحفوظ المحدد مع مقاييسه وأدلته ومصدره."
  },
  "External requests send aggregated evidence from the selected dataset. Ask your data requires your consent before each external request. Keys stay on the server and are never included in exports.": {
    "fr": "Les requêtes externes envoient des données agrégées du jeu sélectionné. Votre consentement est demandé pour chaque requête. Les clés restent sur le serveur et ne sont jamais exportées.",
    "ar": "ترسل الطلبات الخارجية أدلة مجمّعة من مجموعة البيانات المحددة. تتطلب كل مطالبة خارجية موافقتك. تبقى المفاتيح على الخادم ولا تُضمَّن في التصدير."
  },
  "From date": {
    "fr": "Date de début",
    "ar": "من تاريخ"
  },
  "I allow sending this question and aggregated dataset evidence to my selected AI provider for this request.": {
    "fr": "J’autorise l’envoi de cette question et des données agrégées au fournisseur IA choisi pour cette requête.",
    "ar": "أسمح بإرسال هذا السؤال والأدلة المجمّعة إلى مزوّد الذكاء الاصطناعي المحدد لهذا الطلب."
  },
  "I reviewed this preview and approve saving a cleaned version.": {
    "fr": "J’ai vérifié cet aperçu et j’approuve l’enregistrement d’une version nettoyée.",
    "ar": "راجعت هذه المعاينة وأوافق على حفظ إصدار منظَّف."
  },
  "Import a CSV or XLSX file and wait for processing to finish. Then clean, analyze, and export the results.": {
    "fr": "Importez un fichier CSV ou XLSX et attendez la fin du traitement. Nettoyez, analysez et exportez ensuite les résultats.",
    "ar": "استورد ملف CSV أو XLSX وانتظر اكتمال المعالجة. ثم نظّف البيانات وحلّلها وصدّر النتائج."
  },
  "Leave blank to keep the saved key": {
    "fr": "Laissez vide pour conserver la clé enregistrée",
    "ar": "اتركه فارغاً للإبقاء على المفتاح المحفوظ"
  },
  "Loading workbench…": {
    "fr": "Chargement de l’atelier…",
    "ar": "جارٍ تحميل ورشة العمل…"
  },
  "Local mode works without a key. External providers use your own account and model.": {
    "fr": "Le mode local fonctionne sans clé. Les fournisseurs externes utilisent votre compte et votre modèle.",
    "ar": "يعمل الوضع المحلي دون مفتاح. يستخدم المزوّدون الخارجيون حسابك ونموذجك."
  },
  "Map only the fields that apply. Metrics use all matching rows in the selected version. No currency or business meaning is inferred.": {
    "fr": "Associez uniquement les champs utiles. Les indicateurs utilisent toutes les lignes correspondantes de la version choisie. Aucune devise ni signification métier n’est déduite.",
    "ar": "اربط الحقول المناسبة فقط. تستخدم المقاييس جميع الصفوف المطابقة في الإصدار المحدد. لا تُفترَض عملة أو دلالة تجارية."
  },
  "Model": {
    "fr": "Modèle",
    "ar": "النموذج"
  },
  "New column name": {
    "fr": "Nouveau nom de colonne",
    "ar": "اسم العمود الجديد"
  },
  "No analysis yet": {
    "fr": "Aucune analyse pour le moment",
    "ar": "لا يوجد تحليل بعد"
  },
  "No key saved for this provider.": {
    "fr": "Aucune clé enregistrée pour ce fournisseur.",
    "ar": "لا يوجد مفتاح محفوظ لهذا المزوّد."
  },
  "No rows match this result.": {
    "fr": "Aucune ligne ne correspond à ce résultat.",
    "ar": "لا توجد صفوف مطابقة لهذه النتيجة."
  },
  "Not mapped": {
    "fr": "Non associé",
    "ar": "غير مربوط"
  },
  "Open dashboards": {
    "fr": "Ouvrir les tableaux de bord",
    "ar": "فتح لوحات المعلومات"
  },
  "Operations": {
    "fr": "Opérations",
    "ar": "العمليات"
  },
  "Optional filters": {
    "fr": "Filtres facultatifs",
    "ar": "مرشحات اختيارية"
  },
  "Original": {
    "fr": "Original",
    "ar": "أصلي"
  },
  "Power BI package": {
    "fr": "Paquet Power BI",
    "ar": "حزمة Power BI"
  },
  "Preparing…": {
    "fr": "Préparation…",
    "ar": "جارٍ التجهيز…"
  },
  "Preview cleaning": {
    "fr": "Prévisualiser le nettoyage",
    "ar": "معاينة التنظيف"
  },
  "Preview every change before saving a new immutable version. Your original file stays intact.": {
    "fr": "Prévisualisez chaque changement avant d’enregistrer une nouvelle version immuable. Le fichier original est conservé.",
    "ar": "عاين كل تغيير قبل حفظ إصدار جديد ثابت. يبقى الملف الأصلي محفوظاً."
  },
  "Provider": {
    "fr": "Fournisseur",
    "ar": "المزوّد"
  },
  "Remove operation {number}": {
    "fr": "Retirer l’opération {number}",
    "ar": "إزالة العملية {number}"
  },
  "Remove the saved API key": {
    "fr": "Supprimer la clé API enregistrée",
    "ar": "حذف مفتاح API المحفوظ"
  },
  "Replacement value": {
    "fr": "Valeur de remplacement",
    "ar": "القيمة البديلة"
  },
  "Review proposed changes": {
    "fr": "Examiner les changements proposés",
    "ar": "مراجعة التغييرات المقترحة"
  },
  "Rows after": {
    "fr": "Lignes après",
    "ar": "الصفوف بعد التنظيف"
  },
  "Rows before": {
    "fr": "Lignes avant",
    "ar": "الصفوف قبل التنظيف"
  },
  "Run analysis": {
    "fr": "Lancer l’analyse",
    "ar": "تشغيل التحليل"
  },
  "Save AI settings": {
    "fr": "Enregistrer les paramètres IA",
    "ar": "حفظ إعدادات الذكاء الاصطناعي"
  },
  "Save a dashboard": {
    "fr": "Enregistrer un tableau de bord",
    "ar": "حفظ لوحة معلومات"
  },
  "Save cleaned version": {
    "fr": "Enregistrer la version nettoyée",
    "ar": "حفظ الإصدار المنظَّف"
  },
  "Save dashboard": {
    "fr": "Enregistrer le tableau de bord",
    "ar": "حفظ لوحة المعلومات"
  },
  "Saved analysis": {
    "fr": "Analyse enregistrée",
    "ar": "التحليل المحفوظ"
  },
  "Saved dashboard": {
    "fr": "Tableau de bord enregistré",
    "ar": "لوحة المعلومات المحفوظة"
  },
  "Saved snapshot": {
    "fr": "Instantané enregistré",
    "ar": "لقطة محفوظة"
  },
  "Saving…": {
    "fr": "Enregistrement…",
    "ar": "جارٍ الحفظ…"
  },
  "Select a column": {
    "fr": "Choisir une colonne",
    "ar": "اختيار عمود"
  },
  "Select a dashboard": {
    "fr": "Choisir un tableau de bord",
    "ar": "اختيار لوحة معلومات"
  },
  "Select a ready source": {
    "fr": "Choisir une source prête",
    "ar": "اختيار مصدر جاهز"
  },
  "Select an analysis": {
    "fr": "Choisir une analyse",
    "ar": "اختيار تحليل"
  },
  "Set up analysis": {
    "fr": "Configurer une analyse",
    "ar": "إعداد تحليل"
  },
  "Skill guidance": {
    "fr": "Consignes de la compétence",
    "ar": "إرشادات المهارة"
  },
  "Start with a ready source": {
    "fr": "Commencez par une source prête",
    "ar": "ابدأ بمصدر جاهز"
  },
  "The Power BI handoff is a ZIP with data and connection guidance. Open it in Power BI Desktop to build your report.": {
    "fr": "Le paquet Power BI est un ZIP contenant les données et des instructions de connexion. Ouvrez-le dans Power BI Desktop pour créer votre rapport.",
    "ar": "حزمة Power BI ملف ZIP يحتوي البيانات وإرشادات الاتصال. افتحه في Power BI Desktop لإنشاء تقريرك."
  },
  "This dashboard stays tied to its analysis and dataset version.": {
    "fr": "Ce tableau de bord reste lié à son analyse et à sa version de données.",
    "ar": "تبقى لوحة المعلومات مرتبطة بتحليلها وإصدار بياناتها."
  },
  "To date": {
    "fr": "Date de fin",
    "ar": "إلى تاريخ"
  },
  "Version {number}": {
    "fr": "Version {number}",
    "ar": "الإصدار {number}"
  },
  "View analysis results": {
    "fr": "Voir les résultats d’analyse",
    "ar": "عرض نتائج التحليل"
  },
  "View source": {
    "fr": "Voir la source",
    "ar": "عرض المصدر"
  },
  "What should I review in this dataset?": {
    "fr": "Que dois-je examiner dans ce jeu de données ?",
    "ar": "ما الذي ينبغي مراجعته في مجموعة البيانات هذه؟"
  },
  "Working…": {
    "fr": "Traitement…",
    "ar": "جارٍ العمل…"
  },
  "Your AI provider": {
    "fr": "Votre fournisseur IA",
    "ar": "مزوّد الذكاء الاصطناعي"
  },
  "Your answer will appear here with the evidence used. AI answers do not change your data.": {
    "fr": "La réponse et ses justificatifs apparaîtront ici. Les réponses IA ne modifient pas vos données.",
    "ar": "ستظهر إجابتك هنا مع الأدلة المستخدمة. لا تغيّر إجابات الذكاء الاصطناعي بياناتك."
  },
  "Your question": {
    "fr": "Votre question",
    "ar": "سؤالك"
  },
  "Your viewer role can inspect data but cannot save changes.": {
    "fr": "Votre rôle lecteur permet de consulter les données, mais pas d’enregistrer des changements.",
    "ar": "يمكن لدور المشاهد فحص البيانات دون حفظ تغييرات."
  },
  "rows": {
    "fr": "lignes",
    "ar": "صفوف"
  },
  "Trim whitespace": {
    "fr": "Supprimer les espaces superflus",
    "ar": "إزالة المسافات الزائدة"
  },
  "Blank strings to missing": {
    "fr": "Convertir les chaînes vides en valeurs manquantes",
    "ar": "تحويل النصوص الفارغة إلى قيم مفقودة"
  },
  "Remove duplicate rows": {
    "fr": "Supprimer les lignes dupliquées",
    "ar": "إزالة الصفوف المكررة"
  },
  "Remove rows with missing values": {
    "fr": "Supprimer les lignes avec des valeurs manquantes",
    "ar": "إزالة الصفوف ذات القيم المفقودة"
  },
  "Fill missing values": {
    "fr": "Remplir les valeurs manquantes",
    "ar": "تعبئة القيم المفقودة"
  },
  "Rename column": {
    "fr": "Renommer une colonne",
    "ar": "إعادة تسمية عمود"
  },
  "Convert to number": {
    "fr": "Convertir en nombre",
    "ar": "تحويل إلى رقم"
  },
  "Revenue": {
    "fr": "Chiffre d’affaires",
    "ar": "الإيرادات"
  },
  "Cost": {
    "fr": "Coût",
    "ar": "التكلفة"
  },
  "Quantity": {
    "fr": "Quantité",
    "ar": "الكمية"
  },
  "Profit": {
    "fr": "Bénéfice",
    "ar": "الربح"
  },
  "Gross profit": {
    "fr": "Marge brute",
    "ar": "الربح الإجمالي"
  },
  "Margin": {
    "fr": "Marge",
    "ar": "الهامش"
  },
  "Margin (%)": {
    "fr": "Marge (%)",
    "ar": "الهامش (%)"
  },
  "Average row revenue": {
    "fr": "CA moyen par ligne",
    "ar": "متوسط الإيراد لكل صف"
  },
  "Revenue column": {
    "fr": "Colonne du chiffre d’affaires",
    "ar": "عمود الإيرادات"
  },
  "Cost column": {
    "fr": "Colonne du coût",
    "ar": "عمود التكلفة"
  },
  "Quantity column": {
    "fr": "Colonne de quantité",
    "ar": "عمود الكمية"
  },
  "Date column": {
    "fr": "Colonne de date",
    "ar": "عمود التاريخ"
  },
  "Category column": {
    "fr": "Colonne de catégorie",
    "ar": "عمود الفئة"
  },
  "By category": {
    "fr": "Par catégorie",
    "ar": "حسب الفئة"
  },
  "Over time": {
    "fr": "Dans le temps",
    "ar": "عبر الزمن"
  },
  "Analysis includes {included} of {total} source rows.": {
    "fr": "L’analyse inclut {included} lignes sur {total}.",
    "ar": "يتضمن التحليل {included} من {total} صف مصدر."
  },
  "Some mapped values are missing or invalid; review coverage before interpreting totals.": {
    "fr": "Certaines valeurs associées sont manquantes ou invalides ; vérifiez la couverture avant d’interpréter les totaux.",
    "ar": "بعض القيم المربوطة مفقودة أو غير صالحة؛ راجع التغطية قبل تفسير المجاميع."
  },
  "Largest category by row count: {category}": {
    "fr": "Catégorie la plus nombreuse : {category}",
    "ar": "أكبر فئة حسب عدد الصفوف: {category}"
  },
  "Exports & reports": {
    "fr": "Exports et rapports",
    "ar": "التصدير والتقارير"
  },
  "Local evidence assistant": {
    "fr": "Assistant local fondé sur les données",
    "ar": "مساعد الأدلة المحلي"
  },
  "Data quality reviewer": {
    "fr": "Réviseur de qualité des données",
    "ar": "مراجع جودة البيانات"
  },
  "Review missing values, duplicates and safe cleaning choices.": {
    "fr": "Examinez les valeurs manquantes, les doublons et les choix de nettoyage sûrs.",
    "ar": "راجع القيم المفقودة والتكرارات وخيارات التنظيف الآمنة."
  },
  "Business analyst": {
    "fr": "Analyste métier",
    "ar": "محلل الأعمال"
  },
  "Explain confirmed metrics and their calculation scope.": {
    "fr": "Expliquez les indicateurs confirmés et le périmètre de leur calcul.",
    "ar": "اشرح المقاييس المؤكدة ونطاق حسابها."
  },
  "Executive summary": {
    "fr": "Synthèse de direction",
    "ar": "ملخص تنفيذي"
  },
  "Summarize the data and explain what can be concluded.": {
    "fr": "Résumez les données et expliquez les conclusions possibles.",
    "ar": "لخّص البيانات واشرح الاستنتاجات الممكنة."
  },
  "Prioritize quality evidence. Explain missing cells, duplicate rows and the limitations of inferred types. Suggest reviewing cleaning previews; never claim data was modified. Never impute unknown values or infer a column's business meaning.": {
    "fr": "Privilégiez les éléments de qualité. Expliquez les cellules manquantes, les doublons et les limites des types déduits. Proposez de vérifier les aperçus de nettoyage sans prétendre que les données ont été modifiées. N’inventez jamais de valeurs ni de signification métier pour une colonne.",
    "ar": "أعطِ الأولوية لأدلة الجودة. اشرح الخلايا المفقودة والصفوف المكررة وحدود الأنواع المستنتجة. اقترح مراجعة معاينة التنظيف ولا تدّعِ تعديل البيانات. لا تستبدل القيم المجهولة بتخمينات ولا تستنتج المعنى التجاري للأعمدة."
  },
  "Prioritize metrics from the user-confirmed analysis mapping and filters. Explain missing/invalid-value exclusions and scope. Do not assume currency, revenue, cost or causation. If no analysis exists, ask the user to confirm a mapping and run analysis.": {
    "fr": "Privilégiez les indicateurs issus des correspondances et filtres confirmés par l’utilisateur. Expliquez le périmètre et l’exclusion des valeurs manquantes ou invalides. Ne supposez ni devise, ni chiffre d’affaires, ni coût, ni causalité. Sans analyse, demandez de confirmer les correspondances et de lancer une analyse.",
    "ar": "أعطِ الأولوية للمقاييس الناتجة عن ربط الأعمدة والمرشحات التي أكّدها المستخدم. اشرح النطاق واستبعاد القيم المفقودة أو غير الصالحة. لا تفترض عملة أو إيرادات أو تكلفة أو علاقة سببية. إذا لم يوجد تحليل، اطلب تأكيد الربط وتشغيل تحليل."
  },
  "Give a concise summary of verified dataset facts and available confirmed metrics. Separate observed facts from hypotheses. State limitations and one useful next step.": {
    "fr": "Résumez brièvement les faits vérifiés et les indicateurs confirmés disponibles. Distinguez les observations des hypothèses. Précisez les limites et une prochaine étape utile.",
    "ar": "قدّم ملخصاً موجزاً لحقائق مجموعة البيانات المتحققة والمقاييس المؤكدة المتاحة. افصل الحقائق المرصودة عن الفرضيات. اذكر القيود وخطوة تالية مفيدة."
  },
  "The saved API key cannot be decrypted. Re-enter it in AI settings.": {
    "fr": "La clé enregistrée ne peut pas être déchiffrée. Saisissez-la à nouveau dans les paramètres IA.",
    "ar": "تعذّر فك تشفير المفتاح المحفوظ. أعد إدخاله في إعدادات الذكاء الاصطناعي."
  },
  "API key must contain 8 to 4096 non-whitespace characters": {
    "fr": "La clé API doit contenir entre 8 et 4 096 caractères sans espaces",
    "ar": "يجب أن يحتوي مفتاح API على 8 إلى 4096 حرفاً دون مسافات"
  },
  "Choose either a replacement key or clear the saved key": {
    "fr": "Choisissez une nouvelle clé ou supprimez la clé enregistrée",
    "ar": "اختر استبدال المفتاح أو حذف المفتاح المحفوظ"
  },
  "Ready dataset version not found": {
    "fr": "Version prête du jeu de données introuvable",
    "ar": "إصدار مجموعة البيانات الجاهز غير موجود"
  },
  "Completed analysis for this dataset version not found": {
    "fr": "Analyse terminée introuvable pour cette version",
    "ar": "لا يوجد تحليل مكتمل لهذا الإصدار"
  },
  "The AI provider returned an unexpected redirect": {
    "fr": "Le fournisseur IA a renvoyé une redirection inattendue",
    "ar": "أعاد مزوّد الذكاء الاصطناعي إعادة توجيه غير متوقعة"
  },
  "The AI provider response exceeded the size limit": {
    "fr": "La réponse du fournisseur IA dépasse la taille autorisée",
    "ar": "تجاوزت استجابة مزوّد الذكاء الاصطناعي حد الحجم"
  },
  "The AI provider rejected the key or model access. Review AI settings.": {
    "fr": "Le fournisseur IA a refusé la clé ou l’accès au modèle. Vérifiez les paramètres IA.",
    "ar": "رفض المزوّد المفتاح أو الوصول إلى النموذج. راجع إعدادات الذكاء الاصطناعي."
  },
  "The AI provider is rate limited or has insufficient quota. Try later.": {
    "fr": "Le fournisseur IA a atteint sa limite de requêtes ou son quota. Réessayez plus tard.",
    "ar": "بلغ المزوّد حد الطلبات أو نفدت الحصة. حاول لاحقاً."
  },
  "The AI provider could not complete this request. Review the model setting.": {
    "fr": "Le fournisseur IA n’a pas pu traiter la requête. Vérifiez le modèle choisi.",
    "ar": "تعذّر على المزوّد إكمال الطلب. راجع إعداد النموذج."
  },
  "The AI provider could not be reached or returned an unreadable answer.": {
    "fr": "Le fournisseur IA est inaccessible ou a renvoyé une réponse illisible.",
    "ar": "تعذّر الاتصال بالمزوّد أو أعاد إجابة غير مقروءة."
  },
  "Confirm sending the question and aggregate evidence to your selected AI provider.": {
    "fr": "Confirmez l’envoi de la question et des données agrégées au fournisseur IA choisi.",
    "ar": "أكّد إرسال السؤال والأدلة المجمّعة إلى المزوّد المحدد."
  },
  "Save an API key in AI settings before using this provider.": {
    "fr": "Enregistrez une clé API dans les paramètres IA avant d’utiliser ce fournisseur.",
    "ar": "احفظ مفتاح API في الإعدادات قبل استخدام هذا المزوّد."
  },
  "Dataset version not found": {
    "fr": "Version du jeu de données introuvable",
    "ar": "إصدار مجموعة البيانات غير موجود"
  },
  "Wait for this dataset version to finish processing": {
    "fr": "Attendez la fin du traitement de cette version",
    "ar": "انتظر اكتمال معالجة إصدار البيانات"
  },
  "Canonical dataset exceeds the processing limit": {
    "fr": "Le jeu de données dépasse la limite de traitement",
    "ar": "تتجاوز مجموعة البيانات حد المعالجة"
  },
  "Canonical dataset metadata does not match its version": {
    "fr": "Les métadonnées du jeu ne correspondent pas à sa version",
    "ar": "لا تتطابق بيانات التعريف مع إصدار مجموعة البيانات"
  },
  "Canonical dataset is temporarily unavailable": {
    "fr": "Le jeu de données est temporairement indisponible",
    "ar": "مجموعة البيانات غير متاحة مؤقتاً"
  },
  "Cleaning plan not found": {
    "fr": "Plan de nettoyage introuvable",
    "ar": "خطة التنظيف غير موجودة"
  },
  "This cleaning plan cannot be applied": {
    "fr": "Ce plan de nettoyage ne peut pas être appliqué",
    "ar": "لا يمكن تطبيق خطة التنظيف هذه"
  },
  "Cleaned dataset exceeds the processing limit": {
    "fr": "Les données nettoyées dépassent la limite de traitement",
    "ar": "تتجاوز البيانات المنظفة حد المعالجة"
  },
  "The cleaned version could not be saved. Please try again.": {
    "fr": "La version nettoyée n’a pas pu être enregistrée. Réessayez.",
    "ar": "تعذّر حفظ الإصدار المنظَّف. حاول مجدداً."
  },
  "Analysis not found": {
    "fr": "Analyse introuvable",
    "ar": "التحليل غير موجود"
  },
  "Mapped columns must exist in this dataset version": {
    "fr": "Les colonnes associées doivent exister dans cette version",
    "ar": "يجب أن توجد الأعمدة المربوطة في هذا الإصدار"
  },
  "Dashboard not found": {
    "fr": "Tableau de bord introuvable",
    "ar": "لوحة المعلومات غير موجودة"
  },
  "Export exceeds the supported size": {
    "fr": "L’export dépasse la taille autorisée",
    "ar": "يتجاوز التصدير الحجم المدعوم"
  },
  "rows total": {
    "fr": "total des lignes",
    "ar": "إجمالي الصفوف"
  },
  "rows included": {
    "fr": "lignes incluses",
    "ar": "الصفوف المضمّنة"
  },
  "mapping": {
    "fr": "correspondances",
    "ar": "ربط الأعمدة"
  },
  "filters": {
    "fr": "filtres",
    "ar": "المرشحات"
  },
  "missing values": {
    "fr": "valeurs manquantes",
    "ar": "القيم المفقودة"
  },
  "invalid values": {
    "fr": "valeurs invalides",
    "ar": "القيم غير الصالحة"
  },
  "duplicate rows": {
    "fr": "lignes dupliquées",
    "ar": "الصفوف المكررة"
  },
  "formula like text": {
    "fr": "texte ressemblant à une formule",
    "ar": "نص يشبه الصيغ"
  },
  "mixed numeric text": {
    "fr": "types numériques et texte mélangés",
    "ar": "أرقام ونصوص مختلطة"
  },
  "Mixed numeric text": {
    "fr": "Types numériques et texte mélangés",
    "ar": "أرقام ونصوص مختلطة"
  },
  "profiling": {
    "fr": "profilage",
    "ar": "جارٍ التحليل الأولي"
  },
  "validating": {
    "fr": "validation",
    "ar": "جارٍ التحقق"
  },
  "Affected cells": {
    "fr": "Cellules concernées",
    "ar": "الخلايا المتأثرة"
  },
  "Percentage": {
    "fr": "Pourcentage",
    "ar": "النسبة المئوية"
  },
  "Formula like values": {
    "fr": "Valeurs ressemblant à des formules",
    "ar": "قيم تشبه الصيغ"
  },
  "Fraction": {
    "fr": "Proportion",
    "ar": "النسبة"
  },
  "Numeric values": {
    "fr": "Valeurs numériques",
    "ar": "القيم الرقمية"
  },
  "Text values": {
    "fr": "Valeurs textuelles",
    "ar": "القيم النصية"
  },
  "Scope": {
    "fr": "Périmètre",
    "ar": "النطاق"
  },
  "Rows total": {
    "fr": "Total des lignes",
    "ar": "إجمالي الصفوف"
  },
  "Rows included": {
    "fr": "Lignes incluses",
    "ar": "الصفوف المضمّنة"
  },
  "original": {
    "fr": "original",
    "ar": "أصلي"
  },
  "cleaned": {
    "fr": "nettoyé",
    "ar": "منظَّف"
  },
  "Description": {
    "fr": "Description",
    "ar": "الوصف"
  },
  "Mostly numeric column includes text; preserved as text.": {
    "fr": "Une colonne principalement numérique contient du texte ; elle est conservée au format texte.",
    "ar": "يحتوي عمود رقمي في معظمه على نص؛ حُفظ كنص."
  },
  "Exact duplicate occurrences beyond the first; no rows removed.": {
    "fr": "Occurrences exactement identiques après la première ; aucune ligne supprimée.",
    "ar": "تكرارات مطابقة بعد الظهور الأول؛ لم تُحذف أي صفوف."
  },
  "Formula-like strings were kept as text, never evaluated.": {
    "fr": "Les chaînes ressemblant à des formules sont conservées comme texte, sans être exécutées.",
    "ar": "حُفظت النصوص المشابهة للصيغ كنصوص دون تنفيذها."
  }
};
export function translate(text: string, locale: Locale, params: Params = {}): string {
  const value = locale === "en" ? text : messages[text]?.[locale] || text;
  return value.replace(/\{(\w+)\}/g, (match, key:string) => String(params[key] ?? match));
}
export function currentLocale(): Locale { return typeof document !== "undefined" && ["en","fr","ar"].includes(document.documentElement.lang) ? document.documentElement.lang as Locale : "en"; }
type Preferences = {locale:Locale;theme:Theme;setLocale:(value:Locale)=>void;setTheme:(value:Theme)=>void;t:(text:string,params?:Params)=>string};
const Context = createContext<Preferences>({locale:"en",theme:"system",setLocale:()=>{},setTheme:()=>{},t:(value,params)=>translate(value,"en",params)});
export function PreferencesProvider({children}:{children:ReactNode}) {
  const [locale,setLocaleState] = useState<Locale>("en");
  const [theme,setThemeState] = useState<Theme>("system");
  const [ready,setReady] = useState(false);
  useEffect(()=>{
    try { const lang=localStorage.getItem("datapilot.locale"); const mode=localStorage.getItem("datapilot.theme"); if(lang&&["en","fr","ar"].includes(lang))setLocaleState(lang as Locale);if(mode&&["light","dark","system"].includes(mode))setThemeState(mode as Theme); } catch { /* Preferences are optional. */ }
    setReady(true);
    const sync=(event:StorageEvent)=>{if(event.key==="datapilot.locale"&&event.newValue&&["en","fr","ar"].includes(event.newValue))setLocaleState(event.newValue as Locale);if(event.key==="datapilot.theme"&&event.newValue&&["light","dark","system"].includes(event.newValue))setThemeState(event.newValue as Theme);};
    window.addEventListener("storage",sync); return ()=>window.removeEventListener("storage",sync);
  },[]);
  useEffect(()=>{ if(!ready)return; document.documentElement.lang=locale;document.documentElement.dir=locale==="ar"?"rtl":"ltr";try{localStorage.setItem("datapilot.locale",locale);}catch{} },[locale,ready]);
  useEffect(()=>{if(!ready)return;const media=window.matchMedia("(prefers-color-scheme: dark)");const apply=()=>{document.documentElement.dataset.theme=theme==="system"?(media.matches?"dark":"light"):theme;};apply();media.addEventListener("change",apply);try{localStorage.setItem("datapilot.theme",theme);}catch{}return()=>media.removeEventListener("change",apply);},[theme,ready]);
  const t=useCallback((value:string,params:Params={})=>translate(value,locale,params),[locale]);
  const value=useMemo(()=>({locale,theme,setLocale:setLocaleState,setTheme:setThemeState,t}),[locale,theme,t]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n(){ return useContext(Context); }
export function PreferenceControls(){
  const {t,locale,setLocale,theme,setTheme}=useI18n();
  return <div className="preference-controls"><label><span className="sr-only">{t("Language")}</span><select aria-label={t("Language")} value={locale} onChange={e=>setLocale(e.target.value as Locale)}><option value="en">English</option><option value="fr">Français</option><option value="ar">العربية</option></select></label><label><span className="sr-only">{t("Theme")}</span><select aria-label={t("Theme")} value={theme} onChange={e=>setTheme(e.target.value as Theme)}><option value="system">{t("System theme")}</option><option value="light">{t("Light mode")}</option><option value="dark">{t("Dark mode")}</option></select></label></div>;
}
