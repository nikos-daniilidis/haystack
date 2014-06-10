from __future__ import print_function
import os
import re
import string
import pandas as pd

def terms_matched(entry, terms_list_twice=[], terms_list_thrice = []):
    '''
    check that all strings in the list terms_list_twice appear in the string 'entry' exactly twice
    and all strings in the list terms_list_thrice appear in the string 'entry' exactly three times
    returns a boolean
    '''
    for term in terms_list_twice:
        if string.count(entry,term) <> 2:
            return False
    for term in terms_list_thrice:
        if string.count(entry,term) <> 3:
            return False
    return True

def get_content_rest(string_in, tag_str, tag_str_exception = '', reg_expr = ''):
    '''
    Split an xml formatted string. Return a tuple of two strings, content and rest.
    The asssumed format of string_in is:
    <tag_str>content</tag_str>rest
    except if non-empty tag_str_exception is provided, when I assume the format:
    <tag_str>'ignored'reg_expr'ignored'<tag_str_excpetion>rest
    In the latter case, a regular expression string describes the format of the content 
    which gets returned. In both cases, rest is the part of string_in after the end of 
    the </tag_str> or <tag_sre_exception> substring
    '''
    if len(tag_str_exception)==0:
        l = '<'+tag_str+'>'
        h = '</'+tag_str+'>'
    else:
        l = tag_str
        h = tag_str_exception
    if string.find(string_in,l)>-1:
        Ilow =  string.find(string_in,l)+len(l)
    else:
        Ilow = 0
    if string.find(string_in,h)>-1:
        Ihigh = string.find(string_in,h)
    else:
        Ihigh, end_minus = 0,0
        h = ''
    if len(reg_expr) == 0:
        content = string_in[Ilow:Ihigh]
    else:
        p = re.compile(reg_expr)
        m = p.search(string_in[Ilow:Ihigh])
        if m:
            content = m.group()
        else:
            content = ''
    rest = string_in[Ihigh+len(h):]
    return content,rest

def make_author_list(authgrp_str):
    '''
    Make a list of (author, affiliation) tuples for the author group in authgrp_str
    If there is no affiliation in the group, affiliation is set to ''
    Returns: authors, a list of (author,affiliation)
    '''
    try:
        affiliation = authgrp_str.split('</aff>')[0].split('<aff>')[1]
    except:
        affiliation = None
    cnt = 0
    authors = []
    auth_lst = authgrp_str.split('<aff>')[0]
    while 1:
        author, auth_lst = get_content_rest(auth_lst,'author')
        first,restname = get_content_rest(author,'givenname')
        mid, restname = get_content_rest(restname,'middlename')
        last,restname = get_content_rest(restname,'surname')
        authors.append((string.join([first,mid,last]).replace('.',''),affiliation))
        if len(auth_lst)<11:
            break
        cnt += 1
        if cnt>10:
            break
    return authors

def make_pacs_list(string_in):
    '''
    Get the list of pacs numbers.
    '''
    pacs = []
    sub = string_in
    if string.find(sub,'<pacs')>-1 and string.find(sub,'</pacs')>-1:
        count = 0
        while string.find(sub,'<pacscode>')>-1:
            newpacs, sub = get_content_rest(sub,'pacscode')
            pacs.extend([newpacs])
            count += 1
            if count > 10:
                break
    else:
        pacs = []
    return pacs,sub

def regularize_entry(strng):
    '''
    Fix known html formatting issues in the article entry xml strings
    '''
    strout = string.replace(strng,'\n',' ')
    strout = string.replace(strout,'aff >','aff>')
    p = re.compile(' anref="[a-zA-Z0-9]*"')
    m = p.search(strout)
    if m:
        strout = string.replace(strout,m.group(),'')
    p = re.compile(' jcode="[a-zA-Z.= "]*"')
    m = p.search(strout)
    if m:
        strout = string.replace(strout,m.group(),'')
    return strout

def get_authors(string_in):
    '''
    get the list of authors and affiliations. handles the bad xml formatting cases
    '''
    authors = []
    sub = string_in
    if string.find(sub,'</authgrp')>-1:
        count = 0
        while string.find(sub,'<authgrp>')>-1:
            authgrp, sub = get_content_rest(sub,'authgrp')
            al = make_author_list(authgrp)
            authors.extend(al)
            count += 1
            if count > 100:
                break
    else:
        count = 0
        while string.find(sub,'author')>-1:
            authgrp, sub = get_content_rest(sub,'<author','/author>','>[<>./a-zA-Z]*<')
            al = make_author_list('<author'+authgrp+'/author>')
            authors.extend(al)
            count += 1
            if count > 101:
                break
    return authors,sub

def xml_string_to_dataframe(strin):
    '''
    Parse an xml string and put the information in a pandas DataFrame. 
    The xml string consists of repeated blocks of the following form:
    <article doi="00.0000/ABCD.0.0">
    <journal jcode="AB" short="ABCDEF">ABCDEFGH</journal>
    <volume>0</volume>
    <issue printdate="0000-00-00">0</issue>
    <fpage>00</fpage>
    <lpage>00</lpage>
    <seqno>0</seqno>
    <price></price><tocsec>ABC</tocsec>
    <arttype type="article"></arttype><doi>00.0000/ABCD.0.0</doi>
    <title>ABCDE</title>
    <authgrp>
    <author><givenname>AB</givenname><middlename>C</middlename><surname>DEF</surname></author>
    <aff>ABCDE</aff>
    </authgrp>
    <!--
    optionally the group repeats 
    <authgrp>
    <author anref="aA0"><givenname>AB</givenname><middlename>C</middlename><surname>DEF</surname></author>
    <aff>ABCDE</aff>
    </author>
    </authgrp>
    -->
    <history>
    <received date="0000-00-00"/>
    </history>
    <cpyrt>
    <cpyrtdate date="0000" /><cpyrtholder>ABCD</cpyrtholder>
    </cpyrt>
    </article>
    '''
    entries_list = strin.split('</article>')
    entries_list = entries_list[:-1] # drop the last entry: it is empty
    entry_dict = {'journal':[],'print_date':[],'journ_sec':[],'doi':[],'title':[],
                  'authors':[], 'pacs':[], 'publication_year':[]}
    dropped_entries = 0
    for entry in entries_list:
        entry = regularize_entry(entry)
        journal, subsplit = get_content_rest(entry, '<journal','/journal>','>[a-zA-Z ]*<')
        journal = string.replace(journal,'<','')
        journal = string.replace(journal,'>','')
        print_date, subsplit = get_content_rest(subsplit, '<issue','/issue>','[0-9]{4,4}-[0-9]{2,2}-[0-9]{2,2}')
        try:
            journ_sec, subsplit = get_content_rest(subsplit,'<tocsec','/tocsec>','>[a-zA-Z0-9 ,.:"\-]*<')
        except:
            journ_sec = ''
        journ_sec = string.replace(journ_sec,'<','')
        journ_sec = string.replace(journ_sec,'>','')
        doi, subsplit = get_content_rest(subsplit,'doi')
        title, subsplit = get_content_rest(subsplit,'title')
        authors, subsplit = get_authors(subsplit)
        pacs, subsplit = make_pacs_list(subsplit)
        copyrtdate = print_date[:4]
        if len(copyrtdate)!=4:
            print ("Warning: parsed incorrect  date  information for doi:"+doi)
            print ("date: "+copyrtdate)
        entry_dict['journal'].append(journal)
        entry_dict['print_date'].append(print_date)
	try:
	        entry_dict['journ_sec'].append(reorganize_dict[journ_sec])
	except:
		entry_dict['journ_sec'].append(journ_sec)
        entry_dict['doi'].append(doi)
        entry_dict['title'].append(title)
        entry_dict['authors'].append(authors)
        entry_dict['pacs'].append(pacs)
        entry_dict['publication_year'].append((copyrtdate))
    print ("Number of dropped_entries: %d" %dropped_entries)
    out_df = pd.DataFrame(entry_dict)
    return out_df

reorganize_dict = {u'Articles':u'Articles',
		   u'Article':u'Article',
		   u'Fluids, Thermodynamics, and Related Topics':u'Fluids, Thermodynamics, and Related Topics',
		   u'Plasmas, Fluids, Thermodynamics, and Related Topics':u'Plasmas, Fluids, Thermodynamics, and Related Topics',
		   u'Fluids, Plasmas, and Electric Discharges':u'Fluids, Plasmas, and Electric Discharges', 
		   u'Plasma and Beam Physics':u'Plasma and Beam Physics', 
		   u'Nonlinear Dynamics, Fluid Dynamics, Classical Optics, Etc.':u'Nonlinear Dynamics, Fluid Dynamics, Classical Optics, etc.', 
		   u'Nonlinear Dynamics: Fluid Dynamics, Classical Optics, Etc.':u'Nonlinear Dynamics, Fluid Dynamics, Classical Optics, etc.',
		   u'Nonlinear Dynamics, Fluid Dynamics, Classical Optics, etc.':u'Nonlinear Dynamics, Fluid Dynamics, Classical Optics, etc.',
                 u'Atoms and Molecules':u'Atoms and Molecules',
                 u'Atoms, Molecules, and Related Topics':u'Atoms, Molecules, and Related Topics',
                 u'Atomic, Molecular, and Optical Physics':u'Atomic, Molecular, and Optical Physics',
                 u'Solids':u'Solids', 
                 u'Nuclei':u'Nuclei', 
                 u'Atoms, Nuclei, and Particles in Matter':u'Atoms, Nuclei, and Particles in Matter',
                 u'Nuclear Physics':u'Nuclear Physics', 
                 u'Elementary Particles and Fields':u'Elementary Particles and Fields', 
                 u'Condensed Matter: Structure, Etc.':u'Condensed Matter: Structure, etc.', 
                 u'Condensed Matter: Electronic Properties, Etc.':u'Condensed Matter: Electronic Properties, etc.', 
                 u'Condensed Matter: Structure, etc.':u'Condensed Matter: Structure, etc.',
                 u'Condensed Matter: Electronic Properties, etc.':u'Condensed Matter: Electronic Properties, etc.',
                 u'General Physics':u'General Physics',
                 u'General Physics: Statistical and Quantum Mechanics, Quantum Information, etc.':u'General Physics: Statistical and Quantum Mechanics, Quantum Information, etc.', 
                 u'Classical Phenomenology and Applications':u'Classical Phenomenology and Applications',
                 u'Fundamental Phenomenology and Applications':u'Fundamental Phenomenology and Applications',
                 u'Geophysics, Astronomy, and Astrophysics':u'Geophysics, Astronomy, and Astrophysics', 
                 u'Gravitation and Astrophysics':u'Gravitation and Astrophysics',
                 u'Interdisciplinary Physics: Biological Physics, Quantum Information, Etc.':u'Interdisciplinary Physics: Biological Physics, Quantum Information, etc.', 
                 u'Interdisciplinary Physics: Biological Physics, Quantum Information, etc.':u'Interdisciplinary Physics: Biological Physics, Quantum Information, etc.', 
                 u'Soft Matter, Biological, and Interdisciplinary Physics':u'Soft Matter, Biological, and Interdisciplinary Physics',
                 u'Cross-Disciplinary Physics':u'Cross-Disciplinary Physics'}

